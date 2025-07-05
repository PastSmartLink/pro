# dossier_generator.py
# This file contains the core logic for the "Manna Maker" engine's
# Version 3.4 Modular Cognitive Workflow, including the PromptManager
# and the final dossier rendering function.

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, cast

logger = logging.getLogger(__name__)


# ==============================================================================
#  PROMPT MANAGER (Version 3.4 Modular Architecture)
# ==============================================================================

class PromptManager:
    """
    Manages the loading of stage-specific prompts for the modular cognitive workflow.
    This class is central to the IP, allowing for a flexible, maintainable, and
    scalable AI reasoning architecture.
    """
    def __init__(self, prompt_dir: str = "prompts"):
        """
        Initializes the PromptManager.
        
        Args:
            prompt_dir (str): The directory where stage-specific .md prompt files are stored.
        """
        # A robust way to define the path, independent of where the script is called from.
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.prompt_dir = os.path.join(self.base_path, prompt_dir)
        
        if not os.path.isdir(self.prompt_dir):
            logger.warning(f"Prompt directory '{self.prompt_dir}' not found. "
                           f"The system will fail if prompt loading is attempted.")

    def get_prompt(self, stage_name: str) -> str:
        """
        Loads a specific prompt file for a given cognitive stage.

        Args:
            stage_name (str): The name of the stage (e.g., "stage_2_initial_analysis").

        Returns:
            str: The content of the prompt file.
        
        Raises:
            FileNotFoundError: If the specified prompt file does not exist.
        """
        file_path = os.path.join(self.prompt_dir, f"{stage_name}.md")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"CRITICAL PROMPT ERROR: Prompt file not found at '{file_path}'. "
                         f"Ensure the '{stage_name}.md' file exists in the '{self.prompt_dir}' directory.")
            raise

# --- Conceptual Usage within an Orchestrator ---
# The PromptManager is instantiated in the main execution logic (e.g., in an
# ADKApplication's run method or a main runner script). This illustrates how prompts
# for each stage of the cognitive workflow are loaded dynamically.
#
# async def run_cognitive_workflow():
#     try:
#         prompt_manager = PromptManager()
#         
#         # Stage 2: Load the initial analysis prompt
#         stage_2_prompt = prompt_manager.get_prompt("stage_2_initial_analysis")
#         # ... pass stage_2_prompt to the Gemini service ...
#
#         # Stage 4: Load the SUPERGROK inquiry prompt
#         stage_4_prompt = prompt_manager.get_prompt("stage_4_supergrok_inquiry")
#         # ... pass stage_4_prompt to the Gemini service to generate questions...
#
#         # And so on for each stage of the CSMP workflow.
#
#     except FileNotFoundError as e:
#         logger.critical(f"Execution halted due to missing prompt file: {e}")
#         # Handle error gracefully
#
# ==============================================================================
#  RESEARCH TOOL AND RENDERING FUNCTIONS
# ==============================================================================


async def call_perplexity_research_tool(
    query_string: str,
    api_key: str,
    semaphore: asyncio.Semaphore,
    ai_call_timeout: int = 30,
) -> str:
    """
    A standalone function to call the Perplexity API for research purposes,
    as directed by the 'SUPERGROK' stage.
    """
    try:
        # CORRECTED IMPORT: The PerplexityAIService class is in ai_service.py
        from ai_service import PerplexityAIService
    except ImportError:
        logger.critical("CRITICAL: ai_service.py or PerplexityAIService not found for research tool.")
        return "Error: PerplexityAIService dependency not met."

    if not query_string or not isinstance(query_string, str):
        return "Error: No valid query for PPLX."
    if not api_key:
        return "Error: PPLX API Key not configured for research."

    try:
        async with semaphore:
            response_data = await PerplexityAIService.ask_async(
                messages=[{"role": "user", "content": query_string}],
                model="sonar-large-32k-online",
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
    """
    Renders the final structured JSON dossier into a human-readable Markdown report.
    This function remains the final step, taking the output of the modular
    cognitive workflow and presenting it.
    """
    if not isinstance(d_json, dict):
        logger.error("_render_dossier_json_to_markdown: Input d_json is not a dictionary.")
        return "# Error: Dossier data is invalid (not a dictionary). Cannot render."

    # --- EMOJI DEFINITIONS (Expanded) ---
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
        "Netherlands": "🇳🇱", "Italy": "🇮🇹", "England": "🇬🇧", "USA": "🇺🇸",
        "India": "🇮🇳", "Australia": "🇦🇺", "Brazil": "🇧🇷", "Argentina": "🇦🇷",
        "Japan": "🇯🇵", "South Korea": "🇰🇷", "Mexico": "🇲🇽", "Canada": "🇨🇦",
        "Default": "🏳️"
    }
    league_country_map = {
        "soccer_epl": "England",
        "soccer_italy_serie_a": "Italy",
        "soccer_spain_la_liga": "Spain",
        "soccer_germany_bundesliga": "Germany",
        "soccer_france_ligue_one": "France",
        "soccer_usa_mls": "USA",
        "soccer_netherlands_eredivisie": "Netherlands",
        "cricket_ipl": "India",
        "aussierules_afl": "Australia"
    }
    club_emojis_map = {
        "Real Madrid": "👑", "FC Barcelona": "🔵🔴", "Manchester United": "👹",
        "Liverpool": "🦅", "Bayern Munich": "🍺", "Juventus": "🦓",
        "Paris Saint-Germain": "🗼", "Atletico Madrid": "🦊", "Chelsea": "🦁",
        "Arsenal": "🔫", "Manchester City": "🌊", "Tottenham Hotspur": "🐓",
        "Borussia Dortmund": "🐝", "AC Milan": "😈", "Inter Milan": "🐍",
        "AS Roma": "🐺", "Napoli": "🌋", "Ajax": "🛡️", "PSV Eindhoven": "⚡",
        "Feyenoord": "🦁", "Porto": "🐉", "Benfica": "🦅", "Sporting CP": "🦁",
        "Sevilla": "🦇", "Valencia": "🦇", "Villarreal": "🚤", "Leicester City": "🦊",
        "Everton": "🍬", "West Ham United": "⚒️", "Leeds United": "🦚",
        "Bayer Leverkusen": "💊", "RB Leipzig": "🐂", "Lazio": "🦅"
    }

    def get_flag(team_name: str, sport_key: str) -> str:
        if sport_key in league_country_map:
            country = league_country_map[sport_key]
        else:
            country = team_name
        return country_flags_map.get(country, country_flags_map["Default"])

    is_error_report = False
    if "error" in d_json:
        main_dossier_keys = ["executive_summary_narrative", "team_overviews", "overall_prediction"]
        if not any(key in d_json for key in main_dossier_keys):
            is_error_report = True

    if is_error_report:
        err_title_detail = d_json.get('match_title', 'Dossier Generation Error Report')
        err_message_detail = d_json.get('error', 'Unknown error during dossier generation process.')
        exec_summary_partial = d_json.get('executive_summary_narrative')
        debug_info_detail = d_json.get('debug_info')
        raw_response_detail = d_json.get('raw_response_snippet')
        plan_exec_log = d_json.get("plan_execution_notes") or d_json.get("plan_execution_notes_on_error") or d_json.get("plan_errors_and_warnings")

        md_error_render = [
            f"# {sport_emojis_map.get('generic_sport')} Ωmega Scouting Dossier: {err_title_detail}",
            f"## Generation Status: FAILED ☠️",
            f"**Error Detail:** {err_message_detail}\n"
        ]
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
        md_error_render.append(f"\n*Creator's Specializations: AI Pipeline Architect | Generative AI Solutions Developer | LLM Application Specialist | Automated Intelligence Systems Designer*")
        md_error_render.append(f"\n*Report Generated on {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M:%S UTC')}*")
        return "\n".join(md_error_render)

    # --- Main Dossier Rendering Starts Here ---
    md_render = []
    sport_key_data = d_json.get('sport_key', 'generic_sport')
    sport_emoji_title = sport_emojis_map.get(sport_key_data, sport_emojis_map["generic_sport"])

    match_title_full = d_json.get('match_title','N/A')

    baseline_data = d_json.get("baseline_data", {})
    team_a_name_title = baseline_data.get("team_a_name_official")
    team_b_name_title = baseline_data.get("team_b_name_official")

    teams_part_for_title = "Match Analysis"
    league_date_part = ""
    match_title_regex_found = False

    if match_title_full != 'N/A':
        match_title_regex = re.match(r"^(.*?)\s*vs\.?\s*(.*?)\s*\((.*?)\s*-\s*(.*?)\)$", match_title_full, re.IGNORECASE)
        if match_title_regex:
            if not team_a_name_title: team_a_name_title = match_title_regex.group(1).strip()
            if not team_b_name_title: team_b_name_title = match_title_regex.group(2).strip()
            league_name_parsed = match_title_regex.group(3).strip()
            date_parsed = match_title_regex.group(4).strip()
            league_date_part = f"({league_name_parsed} - {date_parsed})"
            match_title_regex_found = True

    if not team_a_name_title: team_a_name_title = "Team A"
    if not team_b_name_title: team_b_name_title = "Team B"

    if not match_title_regex_found:
        if "(" in match_title_full:
            league_date_part = match_title_full[match_title_full.find("("):]
        else:
            league_date_part = f"({sport_emojis_map.get(sport_key_data, '')} {d_json.get('sport_key','Match')})"

    flag_a = get_flag(team_a_name_title, sport_key_data)
    flag_b = get_flag(team_b_name_title, sport_key_data)
    club_emoji_a = club_emojis_map.get(team_a_name_title, "")
    club_emoji_b = club_emojis_map.get(team_b_name_title, "")
    teams_part_for_title = f"{club_emoji_a}{flag_a} {team_a_name_title} <span style='color: #e74c3c; font-weight:bold;'>VS</span> {club_emoji_b}{flag_b} {team_b_name_title}"

    md_render.append(f"# {sport_emoji_title} Ωmega Scouting Dossier {section_emojis['spyglass']}<br>{teams_part_for_title}")
    if league_date_part:
        md_render.append(f"### 🗓️ <small>{league_date_part}</small>\n")
    else:
        md_render.append("\n")

    venue_info = baseline_data.get("venue_name_official")
    time_info_iso = baseline_data.get("commence_time_iso_official")

    if venue_info: md_render.append(f"**🏟️ Venue:** {venue_info}")
    if time_info_iso:
        try:
            dt_obj = datetime.fromisoformat(time_info_iso.replace("Z", "+00:00"))
            time_formatted = dt_obj.strftime('%I:%M %p %Z (UTC %z)')
            md_render.append(f"**⏱️ Kick-off:** {time_formatted}")
        except ValueError:
            md_render.append(f"**⏱️ Kick-off:** {time_info_iso} (Could not parse time)")
    if venue_info or time_info_iso: md_render.append("\n---\n")

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
            current_team_flag = get_flag(team_name_val, sport_key_data)
            club_emoji = club_emojis_map.get(team_name_val, "")
            md_render.append(f"\n### {club_emoji}{current_team_flag} {team_name_val}".strip())
            
            def get_val_or_placeholder(val_dict: Dict[str, Any], key: str, placeholder_texts: List[str], default_ph: str = "[Data Pending AI Derivation]") -> str:
                item_val = val_dict.get(key)
                if item_val is not None and isinstance(item_val, str) and any(ph_text in item_val for ph_text in placeholder_texts): return default_ph
                return item_val if item_val is not None else "N/A"

            common_placeholders = ["[Derive", "##PLACEHOLDER", "Derived Strength", "Derived Concern"]
            md_render.append(f"- **Status & Odds**: {team_item.get('status_and_odds','N/A')}")
            md_render.append(f"- {status_emojis['motivation']} **Motivation**: {get_val_or_placeholder(team_item, 'motivation', common_placeholders)}")
            md_render.append(f"- {status_emojis['dynamics']} **Recent Dynamics**: {get_val_or_placeholder(team_item, 'recent_dynamics', common_placeholders)}")
            md_render.append(f"- **Valuation Summary**: {team_item.get('valuation_summary','N/A')}")

            strengths_list = team_item.get("key_strengths", [])
            if isinstance(strengths_list, list) and strengths_list and not all("Derived Strength" in s for s in strengths_list if isinstance(s, str)): md_render.append(f"- {status_emojis['strength']} **Key Strengths**: {'; '.join(strengths_list)}")
            else: md_render.append(f"- {status_emojis['strength']} **Key Strengths**: *[Pending Full AI Derivation]*")

            concerns_list = team_item.get("key_concerns", [])
            if isinstance(concerns_list, list) and concerns_list and not all("Derived Concern" in c for c in concerns_list if isinstance(c, str)): md_render.append(f"- {status_emojis['concern']} **Key Concerns**: {'; '.join(concerns_list)}")
            else: md_render.append(f"- {status_emojis['concern']} **Key Concerns**: *[Pending Full AI Derivation]*")

    tactical_analysis_content = d_json.get('tactical_analysis_battlegrounds')
    if tactical_analysis_content and isinstance(tactical_analysis_content, str) and tactical_analysis_content != "##PLACEHOLDER_FOR_STAGE_7_NARRATIVE_TACTICAL_EXPANSION##":
        md_render.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds & Game Flow\n{tactical_analysis_content}\n")
    elif tactical_analysis_content:
         md_render.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds & Game Flow\n*[Tactical analysis pending full AI derivation.]*\n")

    key_players_data = d_json.get("key_players_to_watch", [])
    if isinstance(key_players_data, list) and key_players_data and not (len(key_players_data)==1 and isinstance(key_players_data[0],dict) and key_players_data[0].get("player_name")=="[PlayerName]"):
        md_render.append(f"## {section_emojis['players']} Key Players to Watch")
        for player_item in key_players_data:
            if not isinstance(player_item, dict) or player_item.get('player_name') == "[PlayerName]": continue
            player_team_name = player_item.get('team_name','N/A')
            player_flag = get_flag(player_team_name, sport_key_data)
            md_render.append(f"\n- ⭐ **{player_flag} {player_item.get('player_name','N/A')} ({player_team_name})**".strip())
            for key, prefix_text in [("narrative_insight", "Insight"), ("critical_role_detail", "Role"), ("dossier_insight_detail", "Dossier Detail")]:
                val = player_item.get(key)
                if val and isinstance(val, str) and val != "...": md_render.append(f"  - *{prefix_text}*: {val}")
            prop_obs = player_item.get('relevant_prop_observation')
            if prop_obs not in ['N/A', None, '', '...']: md_render.append(f"  - *Prop Observation*: {prop_obs}")

    injury_data = d_json.get("injury_report_impact", [])
    is_real_injury_info = False
    if isinstance(injury_data, list) and injury_data:
        first_injury = injury_data[0]
        if isinstance(first_injury, dict) and not (len(injury_data) == 1 and (first_injury.get("player_name") == "[Player]" or (first_injury.get("player_name") == "N/A" and isinstance(first_injury.get("status"), str) and "No significant" in first_injury.get("status","")))):
            is_real_injury_info = True

    if is_real_injury_info:
        md_render.append(f"\n## {section_emojis['injury']} Injury Report Impact")
        for injury_item in injury_data:
            if isinstance(injury_item,dict) and injury_item.get("player_name") != "[Player]" and injury_item.get("player_name") != "N/A":
                injury_team_name = injury_item.get('team_name','[Team]')
                injury_flag = get_flag(injury_team_name, sport_key_data)
                md_render.append(f"- **{injury_flag} {injury_item.get('player_name','N/A')} ({injury_team_name})**: Status: {injury_item.get('status','[Status]')}. Impact: {injury_item.get('impact_summary','...')}".strip())
    elif isinstance(injury_data, list) and injury_data and isinstance(injury_data[0], dict) and injury_data[0].get("player_name") == "N/A":
        md_render.append(f"\n## {section_emojis['injury']} Injury Report Impact")
        md_render.append(f"- {injury_data[0].get('impact_summary', 'No significant injuries reported.')}")

    gems_data = d_json.get("game_changing_factors_hidden_gems",[])
    default_gem_texts = ["(No distinct hidden gems identified", "(Hidden gems data issue", "(Default: Hidden gems processing"]
    is_real_gems_data = False
    if isinstance(gems_data, list) and gems_data:
        first_gem_dict = gems_data[0]
        if isinstance(first_gem_dict, dict):
            first_gem_detail_text = first_gem_dict.get("detail_explanation","")
            if isinstance(first_gem_detail_text, str) and not any(default_text_marker in first_gem_detail_text for default_text_marker in default_gem_texts):
                is_real_gems_data = True

    if is_real_gems_data:
        md_render.append(f"\n## {section_emojis['gems']} Game-Changing Factors & Hidden Gems")
        for gem_item in gems_data:
             if isinstance(gem_item,dict):
                 gem_title_text = gem_item.get('factor_title','Gem')
                 gem_detail_text = gem_item.get('detail_explanation','N/A')
                 if not isinstance(gem_detail_text, str) or gem_detail_text == "N/A" or "[Derive" in gem_detail_text or any(dt in gem_detail_text for dt in default_gem_texts) : continue
                 md_render.append(f"\n- 💡 **{gem_title_text}:** {gem_detail_text} (Impact: {gem_item.get('impact_on_game','[Derive]')}, Basis: {gem_item.get('supporting_data_type','[Derive]')})")

    alt_perspectives = d_json.get("alternative_perspectives", [])
    if isinstance(alt_perspectives, list) and alt_perspectives:
        md_render.append(f"\n\n## {section_emojis.get('alt_view', '🔄')} Alternative Analytical Viewpoints {section_emojis['spyglass']}")
        for idx, persp_item in enumerate(alt_perspectives, 1):
            if isinstance(persp_item, dict):
                md_render.append(f"\n### Viewpoint {idx}: {persp_item.get('viewpoint_focus', 'Alternative Angle')}")
                md_render.append(f"\n{persp_item.get('alternative_narrative_summary', '*No summary provided for this viewpoint.*')}")
                supporting_args = persp_item.get('supporting_gems_or_arguments', [])
                if isinstance(supporting_args, list) and supporting_args:
                    md_render.append(f"\n  - **Key Supporting Arguments/Gems for this Viewpoint:**")
                    for arg in supporting_args: md_render.append(f"    - {str(arg)}")
        md_render.append("\n")

    prediction_info = d_json.get("overall_prediction")
    if isinstance(prediction_info, dict) and prediction_info.get("predicted_winner") not in ["[Winner/Draw]", None, ""]:
        md_render.append(f"\n## {section_emojis['prediction']} Chief Scout's Final Prediction")
        md_render.append(f"- {status_emojis['winner']} **Predicted Winner**: {prediction_info.get('predicted_winner','N/A')}")
        md_render.append(f"- {status_emojis['score']} **Illustrative Scoreline**: {prediction_info.get('predicted_score_illustrative','[X-Y]')}")
        
        confidence_data = prediction_info.get("confidence_percentage_split")
        if isinstance(confidence_data, dict) and (confidence_data.get('team_a_win_percent',0) > 0 or confidence_data.get('team_b_win_percent',0) > 0 or confidence_data.get('draw_percent_if_applicable',0) > 0):
            md_render.append(f"- {status_emojis['confidence']} **Win Probability Split:**")
            md_render.append(f"  - {flag_a} {team_a_name_title} Win: {confidence_data.get('team_a_win_percent','N/A')}%")
            draw_percent = confidence_data.get('draw_percent_if_applicable', 0)
            if draw_percent is not None and (draw_percent > 0 or str(draw_percent).lower() not in ['0','n/a','none','0.0']):
                md_render.append(f"  - 🤝 Draw: {draw_percent}%")
            md_render.append(f"  - {flag_b} {team_b_name_title} Win: {confidence_data.get('team_b_win_percent','N/A')}%")

        exec_summary_rat = d_json.get('executive_summary_narrative','')
        is_placeholder_summary = isinstance(exec_summary_rat, str) and ("##PLACEHOLDER" in exec_summary_rat or "incomplete" in exec_summary_rat or "failed" in exec_summary_rat)
        
        if isinstance(exec_summary_rat, str) and not is_placeholder_summary and '.' in exec_summary_rat:
            first_sentence = exec_summary_rat.split('.')[0].strip() + '.'
            if first_sentence and len(first_sentence) > 10 : md_render.append(f"- **Brief Rationale (Implied)**: {first_sentence}")

    md_render.append(f"\n\n## {section_emojis.get('complex_view', '🤯')} The Ωmega Perspective: Embracing Complexity")
    md_render.append(
        "The Manna Maker Engine, powering SPORTSΩmegaPRO², is designed to explore multiple analytical pathways. "
        "Different inputs or even the nuanced generative paths of our advanced AI can yield distinct, yet equally insightful, strategic "
        "viewpoints on the same matchup. This dossier, including its primary analysis and any alternative perspectives presented, "
        "shows this capability, offering a richer, more comprehensive understanding than a single deterministic forecast."
    )

    md_render.append(f"\n\n---\n")
    md_render.append(f"**A Hans Johannes Schulte Production for SPORTSΩmegaPRO²**")
    md_render.append(f"\n*System: The Manna Maker Engine*")
    md_render.append(f"\n*Creator's Specializations: AI Pipeline Architect | Generative AI Solutions Developer | LLM Application Specialist | Automated Intelligence Systems Designer*")
    
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
