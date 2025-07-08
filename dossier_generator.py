import asyncio
import json 
import logging
import os
import re 
from datetime import datetime, timezone 
from typing import Dict, List, Optional, Any, Union, cast

logger = logging.getLogger(__name__)

async def call_perplexity_research_tool(
    query_string: str, 
    api_key: str, 
    semaphore: asyncio.Semaphore, 
    ai_call_timeout: int = 30, 
) -> str:
    try:
        from ai_service import PerplexityAIService
    except ImportError:
        logger.critical("CRITICAL: ai_service.py or PerplexityAIService not found for call_perplexity_research_tool.")
        return "Error: PerplexityAIService dependency not met."

    if not query_string or not isinstance(query_string, str):
        return "Error: No valid query for PPLX."
    if not api_key:
        return "Error: PPLX API Key not configured for research."
    
    try:
        response_data = await PerplexityAIService.ask_async(
            messages=[{"role": "user", "content": query_string}],
            model="sonar-pro", 
            api_key=api_key,
            timeout=ai_call_timeout,
            expect_json=False
        )
        if isinstance(response_data, dict) and response_data.get("error"):
            return f"Error: Perplexity API call failed: {response_data.get('error')}"
        if isinstance(response_data, str):
            return response_data
        
        return f"Error: Unexpected response type from PerplexityAIService: {type(response_data)}"

    except Exception as e:
        logger.error(f"PPLX tool err for '{query_string[:30]}...': {e}", exc_info=True)
        return f"Error: PPLX Research Error: {e}"

def _render_dossier_json_to_markdown(d_json: Dict[str, Any]) -> str:
    if not isinstance(d_json, dict):
        logger.error("_render_dossier_json_to_markdown: Input d_json is not a dictionary.")
        return "# Error: Dossier data is invalid (not a dictionary). Cannot render."
    
    # --- EMOJI DEFINITIONS ---
    sport_emojis_map = {
        "basketball_nba": "🏀", "soccer_mls": "⚽️", "icehockey_nhl": "🏒",
        "americanfootball_nfl": "🏈", "baseball_mlb": "⚾️", "soccer_epl": "🇬🇧⚽️", 
        "soccer_uefa_champs_league": "⚽️🏆", "soccer_italy_serie_a": "🇮🇹⚽️", 
        "soccer_spain_la_liga": "🇪🇸⚽️", "soccer_germany_bundesliga": "🇩🇪⚽️", 
        "soccer_france_ligue_one": "🇫🇷⚽️", "soccer_usa_mls": "🇺🇸⚽️", "cricket_ipl": "🏏", 
        "aussierules_afl": "🏉", "soccer_netherlands_eredivisie": "🇳🇱⚽️", 
        "soccer_uefa_nations_league": "🌍⚽️", "generic_sport": "🏅"
    }
    section_emojis = {
        "summary": "📜", "teams": "👥", "tactics": "♟️", "players": "🌟",
        "injury": "🩹", "gems": "💎", "prediction": "🔮", "alt_view": "🔄", 
        "complex_view": "🤯", "notes": "📝", "spyglass": "🔍"
    }
    status_emojis = {
        "strength": "💪", "concern": "⚠️", "motivation": "🔥", "dynamics": "📈",
        "winner": "🏆", "score": "🎯", "confidence": "🧠"
    }
    country_flags_map = {
        "Spain": "🇪🇸", "France": "🇫🇷", "Germany": "🇩🇪", "Portugal": "🇵🇹",
        "Netherlands": "🇳🇱", "Italy": "🇮🇹", "England": "🇬🇧", "United Kingdom": "🇬🇧",
        "USA": "🇺🇸", "United States": "🇺🇸",
        "India": "🇮🇳", "Australia": "🇦🇺", "Brazil": "🇧🇷", "Argentina": "🇦🇷",
        "Japan": "🇯🇵", "South Korea": "🇰🇷", "Mexico": "🇲🇽", "Canada": "🇨🇦",
        "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Denmark": "🇩🇰", "Sweden": "🇸🇪", "Norway": "🇳🇴",
        "Switzerland": "🇨🇭", "Austria": "🇦🇹", "Poland": "🇵🇱", "Turkey": "🇹🇷",
        "Default": "🏳️" 
    }
    league_country_map = {
        "soccer_epl": "England", "soccer_italy_serie_a": "Italy", "soccer_spain_la_liga": "Spain",
        "soccer_germany_bundesliga": "Germany", "soccer_france_ligue_one": "France",
        "soccer_usa_mls": "USA",
        "soccer_netherlands_eredivisie": "Netherlands", "cricket_ipl": "India", "aussierules_afl": "Australia"
    }
    club_emojis_map = {
        "Real Madrid": "👑", "FC Barcelona": "🔵🔴", "Manchester United": "👹", "Liverpool FC": "🦅",
        "Bayern Munich": "🍺", "Juventus": "🦓", "Paris Saint-Germain": "🗼", "Chelsea FC": "🦁",
        "Arsenal FC": "🔫", "Manchester City": "🌊", "Tottenham Hotspur": "🐓","Atletico Madrid": "🐻",
        "Oklahoma City Thunder": "🌩️", "Indiana Pacers": "🏎️", 
        "Boston Celtics": "🍀", "Los Angeles Lakers": "🏆", "Golden State Warriors": "🌉",
        "New York Yankees": "🗽", "Seattle Mariners": "⚓"
    }

    def get_flag_or_sport_icon(team_name: str, sport_key: str) -> str:
        if sport_key in league_country_map:
            country_name = league_country_map[sport_key]
            return country_flags_map.get(country_name, country_flags_map["Default"])
        
        if team_name in country_flags_map:
            return country_flags_map[team_name]
        
        if sport_key == "baseball_mlb":
            return sport_emojis_map.get(sport_key, sport_emojis_map["generic_sport"])
        
        return sport_emojis_map.get(sport_key, country_flags_map["Default"])

    is_error_report = False
    if "error" in d_json and not any(key in d_json for key in ["executive_summary_narrative", "team_overviews", "overall_prediction"]):
        is_error_report = True

    if is_error_report:
        err_title_detail = d_json.get('match_title', 'Dossier Generation Error Report')
        md_error_render = [f"# {sport_emojis_map.get('generic_sport')} Ωmega Scouting Dossier: Error Report",
                           f"## Match: {err_title_detail}",
                           f"## Generation Status: FAILED ☠️",
                           f"**Error Detail:** {d_json.get('error', 'Unknown error.')}\n"]
        exec_summary_partial = d_json.get('executive_summary_narrative') 
        debug_info_detail = d_json.get('debug_info')
        raw_response_detail = d_json.get('raw_response_snippet')
        plan_exec_log = d_json.get("plan_execution_notes") or d_json.get("plan_execution_notes_on_error") or d_json.get("plan_errors_and_warnings")

        if exec_summary_partial and isinstance(exec_summary_partial, str) and \
           "Narrative generation failed" not in exec_summary_partial and \
           "Process incomplete" not in exec_summary_partial:
            md_error_render.append(f"**Partial Analysis (if available):**\n{exec_summary_partial}\n")
        if debug_info_detail:
            md_error_render.append(f"**Debug Info:** {debug_info_detail}\n")
        if raw_response_detail:
             md_error_render.append(f"**AI Response Snippet (from error context):**\n```\n{raw_response_detail}\n```\n")
        
        if isinstance(plan_exec_log, list) and plan_exec_log:
            md_error_render.append(f"\n### {section_emojis['notes']} Plan Execution Log (during error):")
            for note_item in plan_exec_log: 
                if isinstance(note_item, dict):
                    severity = note_item.get("severity", "LOG")
                    step_info = note_item.get("step", "Unknown")
                    msg_info = note_item.get("message", "No detail.")
                    md_error_render.append(f"- **[{severity}] At '{step_info}':** {msg_info}")
                else:
                    md_error_render.append(f"- {str(note_item)}")
            md_error_render.append("\n")
        
        md_error_render.append(f"\n---\n**A Hans Johannes Schulte Production for SPORTSΩmegaPRO²**")
        md_error_render.append(f"\n*System: The Manna Maker Engine*")
        md_error_render.append(f"\n*Generated on {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M:%S UTC')}*")
        return "\n".join(md_error_render)

    # --- Main Dossier Rendering ---
    md_render = []
    sport_key_data = d_json.get('sport_key', 'generic_sport') 
    sport_emoji_title = sport_emojis_map.get(sport_key_data, sport_emojis_map["generic_sport"]) 
    
    match_title_full = d_json.get('match_title','N/A') 
    baseline_data = d_json.get("baseline_data", {})
    team_a_name_title = baseline_data.get("team_a_name_official") 
    team_b_name_title = baseline_data.get("team_b_name_official")
    
    league_date_part_info = ""
    league = ""
    country = ""
    date_str = ""

    if not team_a_name_title or not team_b_name_title or match_title_full == 'N/A':
        if match_title_full != 'N/A':
            match_title_regex = re.match(r"^(.*?)\s*vs\.?\s*(.*?)\s*(?:\((.*)\))?$", match_title_full, re.IGNORECASE)
            if match_title_regex:
                if not team_a_name_title: team_a_name_title = match_title_regex.group(1).strip()
                if not team_b_name_title: team_b_name_title = match_title_regex.group(2).strip()
                if match_title_regex.group(3):
                    league_date_info_raw = match_title_regex.group(3).strip()
                    league_date_split = re.match(r"^(.*?)\s*-\s*(.*?)$", league_date_info_raw)
                    if league_date_split:
                        league = league_date_split.group(1).strip()
                        date_str = league_date_split.group(2).strip()
                        league_date_part_info = f"{league} - {date_str}"
                    else:
                        league_date_part_info = f"{league_date_info_raw}"
            else:
                 if not team_a_name_title: team_a_name_title = "Team A"
                 if not team_b_name_title: team_b_name_title = "Team B"
                 if "(" in match_title_full: league_date_part_info = match_title_full[match_title_full.find("(")+1:-1]
                 else: league_date_part_info = f"{sport_emojis_map.get(sport_key_data, '')} {d_json.get('sport_key','Match Details')}"
        else:
            if not team_a_name_title: team_a_name_title = "Team A"
            if not team_b_name_title: team_b_name_title = "Team B"
            league_date_part_info = f"{sport_emojis_map.get(sport_key_data, '')} {d_json.get('sport_key','Match Details')}"

    # Extract country if possible
    if league_date_part_info:
        # Try to parse country from league name
        for key, val in league_country_map.items():
            if league and league.lower() in key.lower():
                country = val
                break
        if not country and sport_key_data in league_country_map:
            country = league_country_map[sport_key_data]
    if not country:
        country = baseline_data.get("country", "")

    flag_a_icon = get_flag_or_sport_icon(team_a_name_title, sport_key_data)
    flag_b_icon = get_flag_or_sport_icon(team_b_name_title, sport_key_data)
    club_emoji_a_icon = club_emojis_map.get(team_a_name_title, "")
    club_emoji_b_icon = club_emojis_map.get(team_b_name_title, "")

    # Venue and time
    venue_info = baseline_data.get("venue_name_official", d_json.get("venue")) 
    time_info_iso = baseline_data.get("commence_time_iso_official", d_json.get("input", {}).get("commence_time")) or d_json.get("commence_time_iso")

    if time_info_iso:
        try:
            dt_obj = datetime.fromisoformat(str(time_info_iso).replace("Z", "+00:00"))
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=timezone.utc)
            date_str = dt_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            date_str = str(time_info_iso)

    # Compose new title line and info line
    teams_part_for_title = f"{club_emoji_a_icon}{flag_a_icon} {team_a_name_title} **VS** {club_emoji_b_icon}{flag_b_icon} {team_b_name_title} {section_emojis['spyglass']}".replace("  ", " ").strip()
    title_line = f"{sport_emoji_title} {teams_part_for_title}"
    info_line = ""
    info_pieces = []
    if league or country or date_str:
        info_pieces = []
        if league: info_pieces.append(league)
        if country: info_pieces.append(country)
        if date_str: info_pieces.append(date_str)
        info_line = f"🗓️ ({' - '.join(info_pieces)})"
    elif league_date_part_info:
        info_line = f"🗓️ ({league_date_part_info})"
    else:
        info_line = None

    # Title
    md_render.append(f"{title_line}")
    if info_line:
        md_render.append(f"{info_line}\n")
    # No underline!

    # Venue and time (if you want to keep them separately, add here)
    extra_header_info = []
    if venue_info:
        extra_header_info.append(f"**🏟️ Venue:** {venue_info}")
    if time_info_iso:
        try:
            dt_obj = datetime.fromisoformat(str(time_info_iso).replace("Z", "+00:00"))
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=timezone.utc)
            time_formatted = dt_obj.strftime('%B %d, %Y %I:%M %p UTC')
            extra_header_info.append(f"**⏱️ Kick-off:** {time_formatted}")
        except (ValueError, TypeError) as e_time:
            extra_header_info.append(f"**⏱️ Kick-off:** {str(time_info_iso)}")
    if extra_header_info:
        md_render.append(" \\\n".join(extra_header_info) + "\n---\n")

    exec_summary_render = d_json.get('executive_summary_narrative','*Executive summary not available or generation incomplete.*')
    if exec_summary_render == "##PLACEHOLDER_FOR_STAGE_7_NARRATIVE##":
        exec_summary_render = "*Executive summary narrative generation was incomplete.*"
    md_render.append(f"## {section_emojis['summary']} Executive Summary & Narrative\n{exec_summary_render}\n")

    team_overviews_data = d_json.get("team_overviews", []) 
    if isinstance(team_overviews_data, list) and team_overviews_data:
        md_render.append(f"## {section_emojis['teams']} Team Overviews")
        for team_item in team_overviews_data: 
            if not isinstance(team_item, dict): continue
            team_name_val = team_item.get('team_name','N/A')
            current_team_icon = get_flag_or_sport_icon(team_name_val, sport_key_data)
            current_club_emoji = club_emojis_map.get(team_name_val, "")
            md_render.append(f"\n### {current_club_emoji}{current_team_icon} {team_name_val}".replace("  "," ").strip())
            
            def get_val_or_placeholder(val_dict: Dict[str, Any], key: str, placeholder_texts: List[str], default_ph: str = "[Data Pending AI Derivation]") -> str:
                item_val = val_dict.get(key)
                if item_val is not None and isinstance(item_val, str) and any(ph_text in item_val for ph_text in placeholder_texts):
                    return default_ph
                return str(item_val) if item_val is not None else "N/A"

            common_placeholders = ["[Derive", "##PLACEHOLDER", "Derived Strength", "Derived Concern"]
            md_render.append(f"- **Status & Odds**: {team_item.get('status_and_odds','N/A')}")
            md_render.append(f"- {status_emojis['motivation']} **Motivation**: {get_val_or_placeholder(team_item, 'motivation', common_placeholders)}")
            md_render.append(f"- {status_emojis['dynamics']} **Recent Dynamics**: {get_val_or_placeholder(team_item, 'recent_dynamics', common_placeholders)}")
            md_render.append(f"- **Valuation Summary**: {team_item.get('valuation_summary','N/A')}")
            
            strengths_list = team_item.get("key_strengths", []) 
            if isinstance(strengths_list, list) and strengths_list and not all("Derived Strength" in str(s) for s in strengths_list):
                md_render.append(f"- {status_emojis['strength']} **Key Strengths**: {'; '.join(map(str,strengths_list))}")
            else:
                md_render.append(f"- {status_emojis['strength']} **Key Strengths**: *[Pending Full AI Derivation]*")

            concerns_list = team_item.get("key_concerns", []) 
            if isinstance(concerns_list, list) and concerns_list and not all("Derived Concern" in str(c) for c in concerns_list):
                md_render.append(f"- {status_emojis['concern']} **Key Concerns**: {'; '.join(map(str,concerns_list))}")
            else:
                md_render.append(f"- {status_emojis['concern']} **Key Concerns**: *[Pending Full AI Derivation]*")
    
    tactical_analysis_content_from_json = d_json.get('tactical_analysis_battlegrounds')
    if tactical_analysis_content_from_json and isinstance(tactical_analysis_content_from_json, str) and \
       tactical_analysis_content_from_json != "##PLACEHOLDER_FOR_STAGE_7_NARRATIVE_TACTICAL_EXPANSION##":
        is_summary_placeholder = exec_summary_render == "*Executive summary narrative generation was incomplete.*" or \
                                 exec_summary_render == "*Executive summary not available or generation incomplete.*"
        if tactical_analysis_content_from_json.strip() != exec_summary_render.strip() or is_summary_placeholder:
            md_render.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds & Game Flow\n{tactical_analysis_content_from_json}\n")
        else:
            md_render.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds & Game Flow\n*[Tactical analysis section was a duplicate of the executive summary. Specific tactical content may be pending.]*\n")
    elif tactical_analysis_content_from_json:
         md_render.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds & Game Flow\n*[Tactical analysis pending full AI derivation.]*\n")
    else:
        md_render.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds & Game Flow\n*[Tactical analysis not available.]*\n")

    key_players_data = d_json.get("key_players_to_watch", []) 
    if isinstance(key_players_data, list) and key_players_data and not (len(key_players_data)==1 and isinstance(key_players_data[0],dict) and key_players_data[0].get("player_name")=="[PlayerName]"):
        md_render.append(f"## {section_emojis['players']} Key Players to Watch")
        for player_item in key_players_data: 
            if not isinstance(player_item, dict) or player_item.get('player_name') == "[PlayerName]": continue
            player_team_name = player_item.get('team_name','N/A')
            player_icon = get_flag_or_sport_icon(player_team_name, sport_key_data)
            player_club_emoji = club_emojis_map.get(player_team_name, "")
            md_render.append(f"\n- ⭐ **{player_club_emoji}{player_icon} {player_item.get('player_name','N/A')} ({player_team_name})**".replace("  "," ").strip())
            for key, prefix_text in [("narrative_insight", "Insight"), ("critical_role_detail", "Role"), ("dossier_insight_detail", "Dossier Detail")]:
                val = player_item.get(key)
                if val and isinstance(val, str) and val != "...": 
                    md_render.append(f"  - *{prefix_text}*: {val}")
            prop_obs = player_item.get('relevant_prop_observation')
            if prop_obs not in ['N/A', None, '', '...']: 
                md_render.append(f"  - *Prop Observation*: {prop_obs}")
    
    injury_data = d_json.get("injury_report_impact", [])
    is_real_injury_info = False
    if isinstance(injury_data, list) and injury_data:
        first_injury = injury_data[0]
        if isinstance(first_injury, dict) and \
           not (len(injury_data) == 1 and 
                (first_injury.get("player_name") == "[Player]" or 
                 (first_injury.get("player_name") == "N/A" and 
                  isinstance(first_injury.get("status"), str) and 
                  "No significant" in first_injury.get("status","")))):
            is_real_injury_info = True
            
    if is_real_injury_info:
        md_render.append(f"\n## {section_emojis['injury']} Injury Report Impact")
        for injury_item in injury_data:
            if isinstance(injury_item,dict) and injury_item.get("player_name") != "[Player]" and injury_item.get("player_name") != "N/A":
                injury_team_name = injury_item.get('team_name','[Team]')
                injury_icon = get_flag_or_sport_icon(injury_team_name, sport_key_data)
                injury_club_emoji = club_emojis_map.get(injury_team_name, "")
                md_render.append(f"- **{injury_club_emoji}{injury_icon} {injury_item.get('player_name','N/A')} ({injury_team_name})**: Status: {injury_item.get('status','[Status]')}. Impact: {injury_item.get('impact','[Impact]')}")
    elif isinstance(injury_data, list) and injury_data and isinstance(injury_data[0], dict) and injury_data[0].get("player_name") == "N/A":
        md_render.append(f"\n## {section_emojis['injury']} Injury Report Impact")
        md_render.append(f"- {injury_data[0].get('impact_summary', 'No significant injuries reported.')}")

    gems_data = d_json.get("game_changing_factors_hidden_gems",[]) 
    default_gem_texts = ["(No distinct hidden gems identified", "(Hidden gems data issue", "(Default: Hidden gems processing", "[Derive"]
    is_real_gems_data = False
    if isinstance(gems_data, list) and gems_data: 
        for gem_item_check in gems_data:
            if isinstance(gem_item_check, dict):
                detail_text_check = gem_item_check.get("detail_explanation","")
                if isinstance(detail_text_check, str) and not any(marker in detail_text_check for marker in default_gem_texts):
                    is_real_gems_data = True
                    break 
            
    if is_real_gems_data:
        md_render.append(f"\n## {section_emojis['gems']} Game-Changing Factors & Hidden Gems")
        for gem_item in gems_data: 
             if isinstance(gem_item,dict):
                 gem_title_text = gem_item.get('factor_title','Gem')
                 gem_detail_text = gem_item.get('detail_explanation','N/A')
                 if not isinstance(gem_detail_text, str) or gem_detail_text == "N/A" or any(dt in gem_detail_text for dt in default_gem_texts):
                     continue 
                 md_render.append(f"\n- 💡 **{gem_title_text}:** {gem_detail_text} (Impact: {gem_item.get('impact_on_game','[Derive Impact]')}, Basis: {gem_item.get('supporting_data_type','[Derive Data Type]')})")
    elif gems_data:
        md_render.append(f"\n## {section_emojis['gems']} Game-Changing Factors & Hidden Gems\n*[No distinct hidden gems were identified, or data is pending derivation.]*\n")
    
    alt_perspectives = d_json.get("alternative_perspectives", [])
    if isinstance(alt_perspectives, list) and alt_perspectives:
        has_valid_perspective = False
        for persp_item_check in alt_perspectives:
            if isinstance(persp_item_check, dict) and persp_item_check.get('viewpoint_focus', 'Alternative Angle') != 'Alternative Angle':
                has_valid_perspective = True
                break
        
        if has_valid_perspective:
            md_render.append(f"\n\n## {section_emojis.get('alt_view', '🔄')} Alternative Analytical Viewpoints {section_emojis['spyglass']}")
            for idx, persp_item in enumerate(alt_perspectives, 1):
                if isinstance(persp_item, dict) and persp_item.get('viewpoint_focus', 'Alternative Angle') != 'Alternative Angle':
                    md_render.append(f"\n### Viewpoint {idx}: {persp_item.get('viewpoint_focus')}")
                    md_render.append(f"\n{persp_item.get('alternative_narrative_summary', '*No summary provided for this viewpoint.*')}")
                    supporting_args = persp_item.get('supporting_gems_or_arguments', [])
                    if isinstance(supporting_args, list) and supporting_args:
                        md_render.append(f"\n  - **Key Supporting Arguments/Gems for this viewpoint:**")
                        for arg in supporting_args:
                            md_render.append(f"    - {str(arg)}") 
            md_render.append("\n") 

    prediction_info = d_json.get("overall_prediction")
    if isinstance(prediction_info, dict) and prediction_info.get("predicted_winner") not in ["[Winner/Draw]", None, ""]:
        md_render.append(f"\n## {section_emojis['prediction']} Chief Scout's Final Prediction")
        md_render.append(f"- {status_emojis['winner']} **Predicted Winner**: {prediction_info.get('predicted_winner','N/A')}")
        md_render.append(f"- {status_emojis['score']} **Illustrative Scoreline**: {prediction_info.get('predicted_score_illustrative','[X-Y]')}")
        
        confidence_data = prediction_info.get("confidence_percentage_split")
        if isinstance(confidence_data, dict) and ( (isinstance(confidence_data.get('team_a_win_percent'), (int, float)) and confidence_data.get('team_a_win_percent',0) > 0) or \
                                                   (isinstance(confidence_data.get('team_b_win_percent'), (int, float)) and confidence_data.get('team_b_win_percent',0) > 0) or \
                                                   (isinstance(confidence_data.get('draw_percent_if_applicable'), (int, float)) and confidence_data.get('draw_percent_if_applicable',0) > 0) ):
            md_render.append(f"- {status_emojis['confidence']} **Win Probability Split:**")
            
            md_render.append(f"  - {club_emoji_a_icon}{flag_a_icon} {team_a_name_title} Win: {confidence_data.get('team_a_win_percent','N/A')}%".replace("  "," ").strip())
            draw_percent_val = confidence_data.get('draw_percent_if_applicable', 0)
            if draw_percent_val is not None and (isinstance(draw_percent_val, (int,float)) and draw_percent_val > 0): 
                md_render.append(f"  - 🤝 Draw: {draw_percent_val}%") 
            md_render.append(f"  - {club_emoji_b_icon}{flag_b_icon} {team_b_name_title} Win: {confidence_data.get('team_b_win_percent','N/A')}%".replace("  "," ").strip())

        exec_summary_rat_text = d_json.get('executive_summary_narrative','') 
        if not isinstance(exec_summary_rat_text, str): exec_summary_rat_text = ""
        is_placeholder_summary = "##PLACEHOLDER" in exec_summary_rat_text or "incomplete" in exec_summary_rat_text or "failed" in exec_summary_rat_text
        
        if not is_placeholder_summary and '.' in exec_summary_rat_text:
            first_sentence = exec_summary_rat_text.split('.')[0].strip() + '.'
            if first_sentence and len(first_sentence) > 10 : 
                md_render.append(f"- **Brief Rationale (Implied)**: {first_sentence}")

    # --- Ωmega Perspective section, per user request ---
    md_render.append(f"\n\n## 🤯The Manna Maker Cognitive Factory’s 20-stage AGI revolution is designed to explore multiple analytical pathways.")
    md_render.append(
        "Different inputs or even the nuanced generative paths of our advanced AI can yield distinct, yet equally insightful, strategic viewpoints on the same matchup."
    )
    md_render.append(
        "This dossier, including its primary analysis and any alternative perspectives presented, showcases this capability, "
        "offering a richer, more comprehensive understanding than a single deterministic forecast."
    )
    md_render.append("\n### Join the Revolution")
    md_render.append(
        "- **Try a taste**: [aios.icu/generate_super_prompt](https://aios.icu/generate_super_prompt)  \n"
        "- **Follow**: [@pastsmartlink](https://x.com/pastsmartlink) on X  \n"
        "- **Get Involved**: Grab one of 20,000 exclusive ΩMEGA KEY Tokens, earn $250–$1,500/year, and dominate the $100M+ Manna universe!"
    )
    md_render.append("\n---\n")
    md_render.append(
        "A **Hans Johannes Schulte** Production for **AIOS.ICU** (Artificial Intelligence Operating System Intelligence Connection Unit), "
        "igniting the Manna Maker Cognitive Factory’s 20-stage AGI revolution."
    )
    md_render.append("\n**System**: The Manna Maker Engine")
    md_render.append("\n**Creator's Specializations**:")
    md_render.append("- AI Pipeline Architect")
    md_render.append("- Generative AI Solutions Developer")
    md_render.append("- LLM Application Specialist")
    md_render.append("- Automated Intelligence Systems Designer")
    
    ts_utc_str = datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M:%S UTC') 
    prov_info = d_json.get("provenance", {})
    if isinstance(prov_info, dict) and prov_info.get("generation_timestamp_utc"):
        try: 
            ts_from_prov = prov_info["generation_timestamp_utc"]
            if isinstance(ts_from_prov, datetime):
                dt_obj_prov = ts_from_prov.replace(tzinfo=timezone.utc) if ts_from_prov.tzinfo is None else ts_from_prov
            else: 
                dt_obj_prov = datetime.fromisoformat(str(ts_from_prov).replace("Z","+00:00"))
            ts_utc_str = dt_obj_prov.strftime('%B %d, %Y %H:%M:%S UTC')
        except Exception as e_ts: 
            logger.warning(f"Could not parse provenance timestamp '{prov_info['generation_timestamp_utc']}': {e_ts}")
            ts_utc_str = str(prov_info["generation_timestamp_utc"]) 
    md_render.append(f"\n*Generated by SPORTSΩmegaPRO on {ts_utc_str}*")
    
    plan_log_final = d_json.get("plan_execution_notes") or d_json.get("plan_execution_notes_on_error") or d_json.get("plan_errors_and_warnings")
    if isinstance(plan_log_final, list) and plan_log_final:
        md_render.append(f"\n\n### {section_emojis['notes']} Plan Execution Notes:")
        for item_note in plan_log_final:
            if isinstance(item_note, dict):
                md_render.append(f"- **[{item_note.get('severity','LOG')}] At '{item_note.get('step','?')}':** {item_note.get('message','?')}")
            else:
                md_render.append(f"- {str(item_note)}")
                
    return "\n".join(md_render)
