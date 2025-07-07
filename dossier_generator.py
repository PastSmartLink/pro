import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, cast

logger = logging.getLogger(__name__)

class PromptManager:
    def __init__(self, prompt_dir: str = "prompts"):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.prompt_dir = os.path.join(self.base_path, prompt_dir)
        if not os.path.isdir(self.prompt_dir):
            logger.warning(f"Prompt directory '{self.prompt_dir}' not found.")

    def get_prompt(self, stage_name: str) -> str:
        file_path = os.path.join(self.prompt_dir, f"{stage_name}.md")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"CRITICAL PROMPT ERROR: Prompt file not found at '{file_path}'.")
            raise

def render_dossier(dossier_json: Dict[str, Any]) -> str:
    agi_indicators = ["predictive_scenarios", "ethical_review_report", "first_principles_report"]
    if any(key in dossier_json for key in agi_indicators):
        logger.info("Full AGI output detected. Using advanced AGI dossier renderer.")
        return _render_full_agi_dossier_to_markdown(dossier_json)
    else:
        logger.info("Standard dossier output detected. Using standard JSON renderer.")
        return _render_dossier_json_to_markdown(dossier_json)

def _render_full_agi_dossier_to_markdown(d_json: Dict[str, Any]) -> str:
    md_parts = [_render_dossier_json_to_markdown(d_json)]

    md_parts.append("\n---\n# 🧠 Advanced AGI Cognitive Analysis (Stages 10-20)\n")
    md_parts.append("The following sections detail the system's meta-cognitive, strategic, and ethical reasoning processes, providing unparalleled depth and transparency.")

    principles_report = d_json.get("first_principles_report", {})
    if principles_report:
        md_parts.append("\n## 🛡️ Stage 12: First Principles Validation")
        md_parts.append("Deconstruction of the analysis to its axiomatic truths, eliminating unsafe assumptions.")
        validated = principles_report.get("validated_principles", [])
        if validated:
            md_parts.append("\n**Verified Principles:**")
            for item in validated:
                md_parts.append(f"- ✅ {item}")
        invalidated = principles_report.get("invalidated_assumptions", [])
        if invalidated:
            md_parts.append("\n**Rejected Assumptions:**")
            for item in invalidated:
                md_parts.append(f"- ❌ {item}")

    cross_domain_report = d_json.get("cross_domain_mapping_report", {})
    if cross_domain_report:
        md_parts.append("\n## 🌐 Stage 13: Cross-Domain Analogical Insights")
        md_parts.append("Identifying structurally similar problems in unrelated fields to generate novel strategies.")
        analogues = cross_domain_report.get("analogues", [])
        if analogues:
            for item in analogues:
                md_parts.append(f"- **Analogue:** `{item.get('source_domain')}` - `{item.get('analogue_description')}`")
        hypotheses = cross_domain_report.get("novel_hypotheses", [])
        if hypotheses:
            md_parts.append("\n**New Hypotheses Generated:**")
            for item in hypotheses:
                md_parts.append(f"- 💡 {item}")
    
    scenarios = d_json.get("predictive_scenarios", [])
    if scenarios:
        md_parts.append("\n## 🎲 Stage 16: Predictive Scenario Modeling")
        md_parts.append("Mapping the possibility space beyond a single prediction to understand multiple potential futures.")
        for scenario in scenarios:
            prob = scenario.get('probability', 'N/A')
            md_parts.append(f"\n- **Scenario: \"{scenario.get('name', 'Untitled')}\" (Likelihood: {prob}%)**")
            md_parts.append(f"  - *Narrative:* {scenario.get('narrative', '...')}")
            md_parts.append(f"  - *Key Drivers:* {', '.join(scenario.get('drivers', []))}")
            md_parts.append(f"  - ⚫ *Identified 'Black Swan' Event:* {scenario.get('black_swan_event', 'None identified.')}")

    ethical_report = d_json.get("ethical_review_report", {})
    if ethical_report:
        md_parts.append("\n## ⚖️ Stage 17: Ethical Compliance Review")
        md_parts.append("Auditing the analysis for cognitive bias, potential harm, and ethical alignment.")
        risks = ethical_report.get("identified_risks", [])
        if not risks:
            md_parts.append("\n- ✅ **Compliance Status:** No significant ethical risks or biases were detected.")
        else:
            md_parts.append("\n**Identified Risks & Mitigations:**")
            for risk in risks:
                md_parts.append(f"- **Risk:** {risk.get('risk_description', 'N/A')} (Category: `{risk.get('risk_category', 'General')}`)")
                md_parts.append(f"  - **Mitigation Applied:** {risk.get('mitigation_action', 'None.')}")

    validation_report = d_json.get("final_validation_report", {})
    if validation_report:
        md_parts.append("\n## ✅ Stage 20: Final Validation & Quality Assurance")
        md_parts.append("Final adversarial check and internal consistency audit.")
        md_parts.append(f"- **Consistency Check:** {validation_report.get('internal_consistency_check', 'PENDING')}")
        md_parts.append(f"- **Adversarial Challenge:** {validation_report.get('adversarial_challenge_summary', 'PENDING')}")
        md_parts.append(f"- **Final Quality Score:** {validation_report.get('final_quality_score', 'N/A')}/100")
        
    return "\n".join(md_parts)

def _render_dossier_json_to_markdown(d_json: Dict[str, Any]) -> str:
    if not isinstance(d_json, dict):
        logger.error("_render_dossier_json_to_markdown: Input d_json is not a dictionary.")
        return "# Error: Dossier data is invalid (not a dictionary). Cannot render."

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
        "soccer_epl": "England", "soccer_italy_serie_a": "Italy", "soccer_spain_la_liga": "Spain",
        "soccer_germany_bundesliga": "Germany", "soccer_france_ligue_one": "France", "soccer_usa_mls": "USA",
        "soccer_netherlands_eredivisie": "Netherlands", "cricket_ipl": "India", "aussierules_afl": "Australia"
    }
    club_emojis_map = {
        "Real Madrid": "👑", "FC Barcelona": "🔵🔴", "Manchester United": "👹", "Liverpool": "🦅",
        "Bayern Munich": "🍺", "Juventus": "🦓", "Paris Saint-Germain": "🗼", "Atletico Madrid": "🦊",
        "Chelsea": "🦁", "Arsenal": "🔫", "Manchester City": "🌊", "Tottenham Hotspur": "🐓",
        "Borussia Dortmund": "🐝", "AC Milan": "😈", "Inter Milan": "🐍", "AS Roma": "🐺", "Napoli": "🌋",
        "Ajax": "🛡️", "PSV Eindhoven": "⚡", "Feyenoord": "🦁", "Porto": "🐉", "Benfica": "🦅",
        "Sporting CP": "🦁", "Sevilla": "🦇", "Valencia": "🦇", "Villarreal": "🚤",
        "Leicester City": "🦊", "Everton": "🍬", "West Ham United": "⚒️", "Leeds United": "🦚",
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
        if not any(key in d_json for key in ["executive_summary_narrative", "team_overviews", "overall_prediction"]):
            is_error_report = True

    if is_error_report:
        err_title = d_json.get('match_title', 'Dossier Generation Error Report')
        err_msg = d_json.get('error', 'Unknown error during dossier generation.')
        md_error = [f"# {sport_emojis_map.get('generic_sport')} Ωmega Scouting Dossier: {err_title}",
                    f"## Generation Status: FAILED ☠️",
                    f"**Error Detail:** {err_msg}\n"]
        return "\n".join(md_error)

    md = []
    sport_key = d_json.get('sport_key', 'generic_sport')
    sport_emoji = sport_emojis_map.get(sport_key, "🏅")
    match_title = d_json.get('match_title', 'N/A')
    
    baseline = d_json.get("baseline_data", {})
    team_a = baseline.get("team_a_name_official", "Team A")
    team_b = baseline.get("team_b_name_official", "Team B")
    
    flag_a = get_flag(team_a, sport_key)
    flag_b = get_flag(team_b, sport_key)
    club_a = club_emojis_map.get(team_a, "")
    club_b = club_emojis_map.get(team_b, "")
    
    md.append(f"# {sport_emoji} Ωmega Scouting Dossier {section_emojis['spyglass']}<br>{club_a}{flag_a} {team_a} <span style='color: #e74c3c; font-weight:bold;'>VS</span> {club_b}{flag_b} {team_b}")
    md.append(f"### 🗓️ <small>{match_title}</small>\n")

    summary = d_json.get('executive_summary_narrative', '*Executive summary was not generated.*')
    md.append(f"## {section_emojis['summary']} Executive Summary & Narrative\n{summary}\n")

    teams = d_json.get("team_overviews", [])
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

    tactics = d_json.get('tactical_analysis_battlegrounds')
    if tactics: md.append(f"\n## {section_emojis['tactics']} Tactical Battlegrounds\n{tactics}\n")

    players = d_json.get("key_players_to_watch", [])
    if players:
        md.append(f"## {section_emojis['players']} Key Players to Watch")
        for player in players:
            p_team = player.get('team_name', 'N/A')
            p_flag = get_flag(p_team, sport_key)
            md.append(f"\n- ⭐ **{p_flag} {player.get('player_name', 'N/A')} ({p_team})**")

    injuries = d_json.get("injury_report_impact", [])
    if injuries:
        md.append(f"\n## {section_emojis['injury']} Injury Report Impact")
        for injury in injuries:
            i_team = injury.get('team_name','N/A')
            i_flag = get_flag(i_team, sport_key)
            md.append(f"- **{i_flag} {injury.get('player_name','N/A')} ({i_team})**: {injury.get('impact_summary','...')}")

    gems = d_json.get("game_changing_factors_hidden_gems",[])
    if gems:
        md.append(f"\n## {section_emojis['gems']} Hidden Gems & Game-Changing Factors")
        for gem in gems:
            md.append(f"\n- 💡 **{gem.get('factor_title','Gem')}:** {gem.get('detail_explanation','N/A')}")

    alts = d_json.get("alternative_perspectives", [])
    if alts:
        md.append(f"\n\n## {section_emojis.get('alt_view', '🔄')} Alternative Viewpoints")
        for i, alt in enumerate(alts, 1):
            md.append(f"\n### Viewpoint {i}: {alt.get('viewpoint_focus', 'Alternative Angle')}")
            md.append(f"\n{alt.get('alternative_narrative_summary', '')}")

    pred = d_json.get("overall_prediction")
    if pred:
        md.append(f"\n## {section_emojis['prediction']} Final Prediction")
        md.append(f"- {status_emojis['winner']} **Predicted Winner**: {pred.get('predicted_winner','N/A')}")
        md.append(f"- {status_emojis['score']} **Illustrative Scoreline**: {pred.get('predicted_score_illustrative','N/A')}")
        conf = pred.get("confidence_percentage_split")
        if conf:
            md.append(f"- {status_emojis['confidence']} **Win Probability:** {team_a} Win: {conf.get('team_a_win_percent')}% | {team_b} Win: {conf.get('team_b_win_percent')}%")
    
    md.append(f"\n\n---\n**A Hans Johannes Schulte Production for AIOS.ICU, the Intelligence Connection Unit igniting the Manna Maker Cognitive Factory’s 20-stage AGI revolution and infinite possibilities. Try a taste at [aios.icu/generate_super_prompt](https://aios.icu/generate_super_prompt), follow @pastsmartlink on X, grab one of 20,000 exclusive ΩMEGA KEY Tokens, earn $250-$1,500/year, and dominate the $100M+ Manna universe!**")
    
    ts_utc = datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M:%S UTC')
    md.append(f"\n*Generated by the Manna Maker Cognitive OS, powered by AIOS.ICU, on {ts_utc}*")

    return "\n".join(md)
