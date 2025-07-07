import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, cast

logger = logging.getLogger(__name__)

def render_dossier(dossier_json: Dict[str, Any]) -> str:
    """
    Primary and ONLY function for rendering a complete dossier to Markdown.
    It handles both standard and advanced AGI outputs and ensures the
    correct AIOS.ICU branding is always applied.
    """
    if not isinstance(dossier_json, dict):
        logger.error("render_dossier: Input dossier_json is not a dictionary.")
        return "# Error: Dossier data is invalid. Cannot render."

    # --- Start of Rendering Logic ---
    md = []
    
    # Check for fatal error first
    if "error" in dossier_json and not any(key in dossier_json for key in ["executive_summary_narrative", "team_overviews"]):
        err_title = dossier_json.get('match_title', 'Dossier Generation Error Report')
        err_msg = dossier_json.get('error', 'Unknown error during dossier generation.')
        md.append(f"# 🏅 Ωmega Scouting Dossier: {err_title}")
        md.append(f"## Generation Status: FAILED ☠️")
        md.append(f"**Error Detail:** {err_msg}\n")
        return "\n".join(md)

    # --- Data and Emoji Definitions ---
    sport_emojis_map = { "basketball_nba": "🏀", "soccer_mls": "⚽️", "icehockey_nhl": "🏒", "americanfootball_nfl": "🏈", "baseball_mlb": "⚾️", "soccer_epl": "🇬🇧⚽️", "soccer_uefa_champs_league": "⚽️🏆", "soccer_italy_serie_a": "🇮🇹⚽️", "soccer_spain_la_liga": "🇪🇸⚽️", "soccer_germany_bundesliga": "🇩🇪⚽️", "soccer_france_ligue_one": "🇫🇷⚽️", "soccer_usa_mls": "🇺🇸⚽️", "cricket_ipl": "🏏", "aussierules_afl": "🏉", "soccer_netherlands_eredivisie": "🇳🇱⚽️", "soccer_uefa_nations_league": "🌍⚽️", "generic_sport": "🏅" }
    section_emojis = { "summary": "📜", "teams": "👥", "tactics": "♟️", "players": "🌟", "injury": "🩹", "gems": "💎", "prediction": "🔮", "alt_view": "🔄", "complex_view": "🤯", "notes": "📝", "spyglass": "🔍" }
    status_emojis = { "strength": "💪", "concern": "⚠️", "motivation": "🔥", "dynamics": "📈", "winner": "🏆", "score": "🎯", "confidence": "🧠" }
    country_flags_map = { "Spain": "🇪🇸", "France": "🇫🇷", "Germany": "🇩🇪", "Portugal": "🇵🇹", "Netherlands": "🇳🇱", "Italy": "🇮🇹", "England": "🇬🇧", "USA": "🇺🇸", "India": "🇮🇳", "Australia": "🇦🇺", "Brazil": "🇧🇷", "Argentina": "🇦🇷", "Japan": "🇯🇵", "South Korea": "🇰🇷", "Mexico": "🇲🇽", "Canada": "🇨🇦", "Default": "🏳️" }
    league_country_map = { "soccer_epl": "England", "soccer_italy_serie_a": "Italy", "soccer_spain_la_liga": "Spain", "soccer_germany_bundesliga": "Germany", "soccer_france_ligue_one": "France", "soccer_usa_mls": "USA", "soccer_netherlands_eredivisie": "Netherlands", "cricket_ipl": "India", "aussierules_afl": "Australia" }
    club_emojis_map = { "Real Madrid": "👑", "FC Barcelona": "🔵🔴", "Manchester United": "👹", "Liverpool": "🦅", "Bayern Munich": "🍺", "Juventus": "🦓", "Paris Saint-Germain": "🗼", "Atletico Madrid": "🦊", "Chelsea": "🦁", "Arsenal": "🔫", "Manchester City": "🌊", "Tottenham Hotspur": "🐓", "Borussia Dortmund": "🐝", "AC Milan": "😈", "Inter Milan": "🐍", "AS Roma": "🐺", "Napoli": "🌋", "Ajax": "🛡️", "PSV Eindhoven": "⚡", "Feyenoord": "🦁", "Porto": "🐉", "Benfica": "🦅", "Sporting CP": "🦁", "Sevilla": "🦇", "Valencia": "🦇", "Villarreal": "🚤", "Leicester City": "🦊", "Everton": "🍬", "West Ham United": "⚒️", "Leeds United": "🦚", "Bayer Leverkusen": "💊", "RB Leipzig": "🐂", "Lazio": "🦅" }

    def get_flag(team_name: str, sport_key: str) -> str:
        if sport_key in league_country_map:
            country = league_country_map[sport_key]
        else:
            country = team_name
        return country_flags_map.get(country, country_flags_map["Default"])
        
    # --- Main Dossier Rendering ---
    sport_key = dossier_json.get('sport_key', 'generic_sport')
    match_title = dossier_json.get('match_title', 'N/A')
    
    baseline = dossier_json.get("baseline_data", {})
    team_a = baseline.get("team_a_name_official", "Team A")
    team_b = baseline.get("team_b_name_official", "Team B")
    
    flag_a = get_flag(team_a, sport_key)
    flag_b = get_flag(team_b, sport_key)
    club_a = club_emojis_map.get(team_a, "")
    club_b = club_emojis_map.get(team_b, "")
    
    md.append(f"# {sport_emojis_map.get(sport_key, '🏅')} Ωmega Scouting Dossier {section_emojis['spyglass']}<br>{club_a}{flag_a} {team_a} <span style='color: #e74c3c; font-weight:bold;'>VS</span> {club_b}{flag_b} {team_b}")
    md.append(f"### 🗓️ <small>{match_title}</small>\n")

    md.append(f"## {section_emojis['summary']} Executive Summary & Narrative\n{dossier_json.get('executive_summary_narrative', '*Not generated.*')}\n")

    teams = dossier_json.get("team_overviews", [])
    if teams:
        md.append(f"## {section_emojis['teams']} Team Overviews")
        for team in teams:
            team_name = team.get('team_name', 'N/A')
            team_flag = get_flag(team_name, sport_key)
            team_club = club_emojis_map.get(team_name, "")
            md.append(f"\n### {team_club}{team_flag} {team_name}")
            md.append(f"- **Status & Odds**: {team.get('status_and_odds','N/A')}")
            md.append(f"- {status_emojis['motivation']} **Motivation**: {team.get('motivation','N/A')}")
            md.append(f"- {status_emojis['dynamics']} **Recent Dynamics**: {team.get('recent_dynamics','N/A')}")
            md.append(f"- **Valuation Summary**: {team.get('valuation_summary','N/A')}")
            strengths = team.get("key_strengths", [])
            concerns = team.get("key_concerns", [])
            if strengths: md.append(f"- {status_emojis['strength']} **Key Strengths**: {'; '.join(strengths)}")
            if concerns: md.append(f"- {status_emojis['concern']} **Key Concerns**: {'; '.join(concerns)}")

    if dossier_json.get('tactical_analysis_battlegrounds'):
        md.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds\n{dossier_json.get('tactical_analysis_battlegrounds')}\n")

    players = dossier_json.get("key_players_to_watch", [])
    if players:
        md.append(f"## {section_emojis['players']} Key Players to Watch")
        for player in players:
            p_team = player.get('team_name', 'N/A')
            p_flag = get_flag(p_team, sport_key)
            md.append(f"\n- ⭐ **{p_flag} {player.get('player_name', 'N/A')} ({p_team})**")

    injuries = dossier_json.get("injury_report_impact", [])
    if injuries:
        md.append(f"\n## {section_emojis['injury']} Injury Report Impact")
        for injury in injuries:
            i_team = injury.get('team_name','N/A')
            i_flag = get_flag(i_team, sport_key)
            md.append(f"- **{i_flag} {injury.get('player_name','N/A')} ({i_team})**: {injury.get('impact_summary','...')}")

    gems = dossier_json.get("game_changing_factors_hidden_gems",[])
    if gems:
        md.append(f"\n## {section_emojis['gems']} Hidden Gems & Game-Changing Factors")
        for gem in gems:
            md.append(f"\n- 💡 **{gem.get('factor_title','Gem')}:** {gem.get('detail_explanation','N/A')}")

    alts = dossier_json.get("alternative_perspectives", [])
    if alts:
        md.append(f"\n\n## {section_emojis.get('alt_view', '🔄')} Alternative Viewpoints")
        for i, alt in enumerate(alts, 1):
            md.append(f"\n### Viewpoint {i}: {alt.get('viewpoint_focus', 'Alternative Angle')}")
            md.append(f"\n{alt.get('alternative_narrative_summary', '')}")

    pred = dossier_json.get("overall_prediction")
    if pred:
        md.append(f"\n## {section_emojis['prediction']} Final Prediction")
        md.append(f"- {status_emojis['winner']} **Predicted Winner**: {pred.get('predicted_winner','N/A')}")
        md.append(f"- {status_emojis['score']} **Illustrative Scoreline**: {pred.get('predicted_score_illustrative','N/A')}")
        conf = pred.get("confidence_percentage_split")
        if conf:
            md.append(f"- {status_emojis['confidence']} **Win Probability:** {team_a} Win: {conf.get('team_a_win_percent')}% | {team_b} Win: {conf.get('team_b_win_percent')}%")

    # --- THE FINAL, CORRECTED FOOTER ---
    md.append(f"\n\n---\n**A Hans Johannes Schulte Production for AIOS.ICU, the Intelligence Connection Unit igniting the Manna Maker Cognitive Factory’s 20-stage AGI revolution and infinite possibilities. Try a taste at [aios.icu/generate_super_prompt](https://aios.icu/generate_super_prompt), follow @pastsmartlink on X, grab one of 20,000 exclusive ΩMEGA KEY Tokens, earn $250-$1,500/year, and dominate the $100M+ Manna universe!**")
    
    ts_utc = datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M:%S UTC')
    md.append(f"\n*Generated by the Manna Maker Cognitive OS, powered by AIOS.ICU, on {ts_utc}*")

    return "\n".join(md)
