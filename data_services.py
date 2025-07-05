# data_services.py
import os
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, cast
from cachetools import TTLCache
import aiohttp

from utils import (
    get_cached_odds_async,
    normalize_team_name_util,
    get_valuation_from_club_data_util,
    SPORTS_DISPLAY
)
from accumulator_logic import american_to_decimal
from ai_service import PerplexityAIService

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

full_match_details_cache = TTLCache(maxsize=50, ttl=3600 * 4)

async def _internal_fetch_sentiment_for_baseline_ds(
    match_details: Dict[str, Any],
    api_semaphore: asyncio.Semaphore,
    sentiment_cache_instance: TTLCache,
    perplexity_api_key: str,
    ai_call_timeout: int
) -> Dict[str, Any]:
    gid = match_details.get('game_id', 'UNKNOWN_GAME_ID')
    ht = match_details.get('home_team', 'TeamA')
    at = match_details.get('away_team', 'TeamB')
    sdisp = match_details.get('sport_display', 'Sport')

    final_cache_key = f"sentiment_v4_{gid}"
    cached_item = sentiment_cache_instance.get(final_cache_key)
    if cached_item:
        logger.debug(f"DS Internal Sentiment CACHE HIT for {gid}")
        return cast(Dict[str, Any], cached_item)
    logger.debug(f"DS Internal Sentiment CACHE MISS for {gid}")

    sent_prompt = f"Analyze sentiment for {sdisp} match: {ht} vs {at}. Provide insights and scores. STRICTLY JSON output format required. Example: {{\"home_sentiment_details\": {{\"score\": 0.0, \"factors\": []}}, \"away_sentiment_details\": {{\"score\": 0.0, \"factors\": []}}, \"sentiment_sources\": [{{\"name\": \"Source\", \"url\": \"URL\"}}]}}"
    messages = [{'role': 'system', 'content': 'You are an expert sports sentiment analyst outputting STRICT JSON.'}, {'role': 'user', 'content': sent_prompt}]
    error_response_structure = {'error': True, 'error_detail': 'Sentiment fetch failed', 'home_sentiment_details': {}, 'away_sentiment_details': {}, 'sentiment_sources': []}

    async with api_semaphore:
        # <<< FINAL FIX: Using 'llama-3-sonar-small-32k-online' for this less critical task for speed/cost. >>>
        ai_data = await PerplexityAIService.ask_async(
            messages=messages, model="llama-3-sonar-small-32k-online",
            api_key=perplexity_api_key, timeout=ai_call_timeout, expect_json=True
        )
        logger.debug(f"DS: Perplexity sentiment response for {gid}: {json.dumps(ai_data, indent=2)}")

    if not isinstance(ai_data, dict) or ai_data.get("error"):
        err_detail = ai_data.get("error", "Unknown AI service error") if isinstance(ai_data, dict) else str(ai_data)
        logger.error(f"DS Internal Sentiment API Error {gid}: {err_detail}")
        return {**error_response_structure, 'error_detail': err_detail}
    try:
        hs_details = ai_data.get('home_sentiment_details', {})
        as_details = ai_data.get('away_sentiment_details', {})
        hsv = str(hs_details.get('score', '')).strip().lower()
        asv = str(as_details.get('score', '')).strip().lower()
        parsed_response = {
            'home_sentiment_details': {
                'score': float(hsv) if hsv and hsv not in ["n/a", "none", "null"] else None,
                'factors': hs_details.get('factors', []) if isinstance(hs_details.get('factors'), list) else []
            },
            'away_sentiment_details': {
                'score': float(asv) if asv and asv not in ["n/a", "none", "null"] else None,
                'factors': as_details.get('factors', []) if isinstance(as_details.get('factors'), list) else []
            },
            'sentiment_sources': [s for s in ai_data.get('sentiment_sources', []) if isinstance(s, dict) and 'name' in s and 'url' in s]
        }
        sentiment_cache_instance[final_cache_key] = parsed_response
        return parsed_response
    except Exception as e:
        logger.error(f"DS Internal Sentiment Validation Exception {gid}: {e}. Data: {ai_data}", exc_info=True)
        return {**error_response_structure, 'error_detail': f"Sentiment validation error: {e}"}

async def _internal_get_perplexity_prediction_ds(
    match_details: Dict[str, Any], 
    api_semaphore: asyncio.Semaphore,
    prediction_cache_instance: TTLCache,
    perplexity_api_key: str,
    ai_call_timeout: int
) -> Dict[str, Any]:
    gid = match_details.get('game_id', 'UNKNOWN_GAME_ID')
    final_cache_key = f"pplx_pred_v5_{gid}"
    cached_item = prediction_cache_instance.get(final_cache_key)
    if cached_item:
        logger.debug(f"DS Internal Prediction CACHE HIT for {gid}")
        return cast(Dict[str, Any], cached_item)
    logger.debug(f"DS Internal Prediction CACHE MISS for {gid}")

    pred_prompt_full = f"As SPORTSΩmega AI Analyst for {match_details.get('sport_display')} match: {match_details.get('home_team')} vs {match_details.get('away_team')}, provide detailed game prediction insights. Match Details for context: Commence: {match_details.get('commence_time')}, HomeOddsRaw: {match_details.get('home_odds_raw')}, AwayOddsRaw: {match_details.get('away_odds_raw')}, HomeSentScore: {match_details.get('home_sentiment_details', {}).get('score')}, AwaySentScore: {match_details.get('away_sentiment_details', {}).get('score')}. STRICTLY output JSON format: {{\"winner\": \"Team Name/Draw\", \"confidence_score\": 0.0-1.0 (float), \"predicted_score\": \"X-Y\", \"reasoning_narrative\": \"Detailed reasoning.\", \"key_factors_list\": [\"Factor 1\", \"Factor 2\"], \"hidden_gems\": [\"Gem 1\"], \"sources_list\": [{{\"name\": \"Source Name\", \"url\": \"Source URL\"}}]}}. Ensure all keys are present."
    messages = [{'role': 'system', 'content': 'SPORTSΩmega AI Analyst. Output ONLY strict, complete JSON according to user examples.'}, {'role': 'user', 'content': pred_prompt_full}]
    error_response_structure = {'error': True, 'error_detail': 'Prediction fetch failed', 'winner': None, 'confidence_score': None, 'predicted_score': 'N/A', 'reasoning_narrative': 'N/A', 'key_factors_list': [], 'hidden_gems': [], 'sources_list': []}

    async with api_semaphore:
        # <<< FINAL FIX: Using 'sonar-pro' as confirmed by your successful test. >>>
        # This is the most powerful and up-to-date model for this critical prediction task.
        ai_data = await PerplexityAIService.ask_async(
            messages=messages, model="sonar-pro",
            api_key=perplexity_api_key, timeout=ai_call_timeout, expect_json=True
        )
        logger.debug(f"DS: Perplexity prediction response for {gid}: {json.dumps(ai_data, indent=2)}")

    if not isinstance(ai_data, dict) or ai_data.get("error"):
        err_detail = ai_data.get("error", "Unknown AI service error for prediction") if isinstance(ai_data, dict) else str(ai_data)
        logger.error(f"DS Internal Prediction API Error {gid}: {err_detail}")
        return {**error_response_structure, 'error_detail': err_detail}
    try:
        csf = None
        if 'confidence_score' in ai_data:
            try:
                cs_raw = ai_data['confidence_score']; cf = float(cs_raw); csf = cf if 0.0 <= cf <= 1.0 else None
            except: pass
        parsed_response = {
            'winner': ai_data.get('winner', 'Analysis Incomplete' if csf is None else 'N/A'),
            'confidence_score': csf,
            'predicted_score': ai_data.get('predicted_score', 'N/A'),
            'reasoning_narrative': ai_data.get('reasoning_narrative', 'Detailed analysis may be incomplete.'),
            'key_factors_list': ai_data.get('key_factors_list', []) if isinstance(ai_data.get('key_factors_list'), list) else [],
            'hidden_gems': ai_data.get('hidden_gems', []) if isinstance(ai_data.get('hidden_gems'), list) else [],
            'sources_list': [s for s in ai_data.get('sources_list', []) if isinstance(s, dict) and 'name' in s and 'url' in s]
        }
        if not parsed_response['winner'] or parsed_response['confidence_score'] is None:
            logger.warning(f"DS Pred {gid}: Missing winner/conf. Data: {ai_data} -> Parsed: {parsed_response}")
        prediction_cache_instance[final_cache_key] = parsed_response
        return parsed_response
    except Exception as e:
        logger.error(f"DS Internal Pred Validation Exc {gid}: {e}. Data: {ai_data}", exc_info=True)
        return {**error_response_structure, 'error_detail': f"Prediction validation error: {e}"}

async def _internal_fetch_news_for_baseline_ds(
    match_details: Dict[str, Any],
    api_semaphore: asyncio.Semaphore,
    news_cache_instance: TTLCache,
    perplexity_api_key: str,
    ai_call_timeout: int
) -> str:
    gid = match_details.get('game_id', 'UNKNOWN_GAME_ID')
    ht = match_details.get('home_team', 'TeamA'); at = match_details.get('away_team', 'TeamB'); sdisp = match_details.get('sport_display', 'Sport')
    final_cache_key = f"baseline_news_v2_{gid}"
    cached_item = news_cache_instance.get(final_cache_key)
    if cached_item: return cast(str, cached_item)

    news_prompt = f"Provide a concise news summary (1-2 sentences, max 50 words) relevant to the upcoming {sdisp} match between {ht} and {at}, focusing on critical team news, injuries, or form that could impact the game. If no significant specific news, state that. Output plain text only."
    messages = [{'role': 'system', 'content': 'You are an ultra-concise sports news summarizer, outputting only plain text for the most critical match-relevant news.'}, {'role': 'user', 'content': news_prompt}]
    
    async with api_semaphore:
        # <<< FINAL FIX: Using a fast, small model for this simple task. >>>
        news_summary = await PerplexityAIService.ask_async(
            messages=messages, model="llama-3-sonar-small-32k-online",
            api_key=perplexity_api_key, timeout=ai_call_timeout, expect_json=False
        )
        logger.debug(f"DS: Perplexity news response for {gid}: {news_summary}")

    if isinstance(news_summary, dict) and news_summary.get("error"):
        return f"Error: News unavailable ({news_summary.get('error','Unknown AI err')})"
    if not isinstance(news_summary, str) or not news_summary.strip() or news_summary.lower().startswith("error:"):
        return "No significant news updates found."
    cleaned_summary = news_summary.strip()
    news_cache_instance[final_cache_key] = cleaned_summary
    return cleaned_summary

async def get_minimal_match_details_async(
    game_id: str,
    sport_key_context: str,
    session: aiohttp.ClientSession
) -> Dict[str, Any]:
    odds_data = await get_cached_odds_async(sport_key_context, session)
    if not odds_data:
        return {'error': f"No odds data found for sport {sport_key_context} via get_cached_odds_async"}

    for game in odds_data:
        if not isinstance(game, dict): continue
        if game.get('id') == game_id:
            ht_orig, at_orig = game.get('home_team'), game.get('away_team')
            if not isinstance(ht_orig, str) or not isinstance(at_orig, str):
                logger.warning(f"Skipping game with non-string team names: ht={ht_orig}, at={at_orig} for game ID {game_id}")
                continue

            ht_disp = normalize_team_name_util(ht_orig, sport_key_context)
            at_disp = normalize_team_name_util(at_orig, sport_key_context)

            bookmakers = game.get('bookmakers', [])
            h2h_market, spreads_market, totals_market = None, None, None
            preferred_bks = ['draftkings', 'fanduel', 'betmgm', 'caesars', 'betrivers', 'pointsbetus']

            temp_bk_data = [b for b in bookmakers if isinstance(b, dict) and b.get('key') in preferred_bks and b.get('markets')]
            selected_bookmakers_iter = temp_bk_data if temp_bk_data else [b for b in bookmakers if isinstance(b, dict) and b.get('markets')]

            for b_data_iter in selected_bookmakers_iter:
                if not h2h_market and isinstance(b_data_iter.get('markets'), list): h2h_market = next((m for m in b_data_iter['markets'] if isinstance(m, dict) and m.get('key') == 'h2h' and m.get('outcomes')), None)
                if not spreads_market and isinstance(b_data_iter.get('markets'), list): spreads_market = next((m for m in b_data_iter['markets'] if isinstance(m, dict) and m.get('key') == 'spreads' and m.get('outcomes')), None)
                if not totals_market and isinstance(b_data_iter.get('markets'), list): totals_market = next((m for m in b_data_iter['markets'] if isinstance(m, dict) and m.get('key') == 'totals' and m.get('outcomes')), None)
                if h2h_market and spreads_market and totals_market and b_data_iter.get('key') in preferred_bks:
                    break
            
            if not (h2h_market and spreads_market and totals_market):
                for b_full_iter in bookmakers:
                    if not isinstance(b_full_iter, dict) or not b_full_iter.get('markets'): continue
                    if not h2h_market and isinstance(b_full_iter.get('markets'), list): h2h_market = next((m for m in b_full_iter['markets'] if isinstance(m, dict) and m.get('key') == 'h2h' and m.get('outcomes')), h2h_market)
                    if not spreads_market and isinstance(b_full_iter.get('markets'), list): spreads_market = next((m for m in b_full_iter['markets'] if isinstance(m, dict) and m.get('key') == 'spreads' and m.get('outcomes')), spreads_market)
                    if not totals_market and isinstance(b_full_iter.get('markets'), list): totals_market = next((m for m in b_full_iter['markets'] if isinstance(m, dict) and m.get('key') == 'totals' and m.get('outcomes')), totals_market)

            home_odds_raw, away_odds_raw, draw_odds_raw = None, None, None
            if h2h_market and isinstance(h2h_market.get('outcomes'), list):
                home_odds_raw = next((o.get('price') for o in h2h_market['outcomes'] if isinstance(o, dict) and o.get('name') == ht_orig), None)
                away_odds_raw = next((o.get('price') for o in h2h_market['outcomes'] if isinstance(o, dict) and o.get('name') == at_orig), None)
                draw_odds_raw = next((o.get('price') for o in h2h_market['outcomes'] if isinstance(o, dict) and o.get('name') == 'Draw'), None)

            home_spread_pts, home_spread_odds_raw, away_spread_pts, away_spread_odds_raw = None, None, None, None
            if spreads_market and isinstance(spreads_market.get('outcomes'), list):
                sh_outcome = next((o for o in spreads_market['outcomes'] if isinstance(o, dict) and o.get('name') == ht_orig), None)
                sa_outcome = next((o for o in spreads_market['outcomes'] if isinstance(o, dict) and o.get('name') == at_orig), None)
                if sh_outcome and isinstance(sh_outcome, dict): home_spread_pts, home_spread_odds_raw = sh_outcome.get('point'), sh_outcome.get('price')
                if sa_outcome and isinstance(sa_outcome, dict): away_spread_pts, away_spread_odds_raw = sa_outcome.get('point'), sa_outcome.get('price')

            total_line_val, total_over_odds_raw, total_under_odds_raw = None, None, None
            if totals_market and isinstance(totals_market.get('outcomes'), list):
                ov_outcome = next((o for o in totals_market['outcomes'] if isinstance(o, dict) and 'over' in o.get('name', '').lower()), None)
                un_outcome = next((o for o in totals_market['outcomes'] if isinstance(o, dict) and 'under' in o.get('name', '').lower()), None)
                if ov_outcome and isinstance(ov_outcome, dict): total_over_odds_raw, total_line_val = ov_outcome.get('price'), ov_outcome.get('point')
                if un_outcome and isinstance(un_outcome, dict): total_under_odds_raw = un_outcome.get('price')
                if total_line_val is None and un_outcome and isinstance(un_outcome, dict) and un_outcome.get('point') is not None: total_line_val = un_outcome.get('point')

            return {
                'game_id': game_id,
                'sport_key': sport_key_context,
                'sport_display': SPORTS_DISPLAY.get(sport_key_context, sport_key_context.replace("_", " ").title()),
                'home_team': ht_disp,
                'away_team': at_disp,
                'home_team_official_odds_name': ht_orig,
                'away_team_official_odds_name': at_orig,
                'commence_time': game.get('commence_time', 'N/A'),
                'home_odds_raw': home_odds_raw,
                'away_odds_raw': away_odds_raw,
                'draw_odds_raw': draw_odds_raw,
                'home_spread_points': home_spread_pts,
                'home_spread_odds_raw': home_spread_odds_raw,
                'away_spread_points': away_spread_pts,
                'away_spread_odds_raw': away_spread_odds_raw,
                'total_over_under_line': total_line_val,
                'total_over_odds_raw': total_over_odds_raw,
                'total_under_odds_raw': total_under_odds_raw,
                'home_valuation': get_valuation_from_club_data_util(ht_disp, sport_key_context),
                'away_valuation': get_valuation_from_club_data_util(at_disp, sport_key_context),
                'home_odds': american_to_decimal(home_odds_raw) if home_odds_raw is not None else None,
                'away_odds': american_to_decimal(away_odds_raw) if away_odds_raw is not None else None,
                'draw_odds': american_to_decimal(draw_odds_raw) if draw_odds_raw is not None else None
            }
    logger.warning(f"Match ID {game_id} not found in odds for sport {sport_key_context}")
    return {'error': f"Match ID {game_id} not found for sport {sport_key_context} after fetching odds."}

async def get_full_match_details_for_dossier_baseline(
    match_id: str, sport_key: str, team_a_name_input: str, team_b_name_input: str,
    http_session: aiohttp.ClientSession, api_semaphore: asyncio.Semaphore,
    sentiment_cache_instance: TTLCache, prediction_cache_instance: TTLCache,
    news_cache_instance: TTLCache, perplexity_api_key_val: str, ai_call_timeout_val: int
) -> Dict[str, Any]:
    cache_key = f"dossier_baseline__{match_id}__{sport_key}"
    cached_val = full_match_details_cache.get(cache_key)
    if cached_val:
        logger.info(f"DS CACHE HIT for baseline: {match_id}")
        return cast(Dict[str, Any], cached_val)

    logger.info(f"DS CACHE MISS for baseline: {match_id}. Fetching.")
    match_core_details = await get_minimal_match_details_async(match_id, sport_key, http_session)
    if 'error' in match_core_details:
        logger.error(f"DS: Core details fail {match_id}: {match_core_details['error']}")
        return {"error": f"Core details fetch fail: {match_core_details['error']}"}

    ht_off = match_core_details.get("home_team", team_a_name_input)
    at_off = match_core_details.get("away_team", team_b_name_input)
    sdisp_name = match_core_details.get("sport_display", sport_key.replace("_", " ").title())
    ctime_str = match_core_details.get("commence_time", "N/A")

    match_date = ctime_str.split('T')[0] if isinstance(ctime_str, str) and 'T' in ctime_str else "TBD"

    ai_input_md = {
        "game_id": match_id, "sport_key": sport_key, "sport_display": sdisp_name,
        "home_team": ht_off, "away_team": at_off, "commence_time": ctime_str,
        "home_valuation": match_core_details.get('home_valuation'),
        "away_valuation": match_core_details.get('away_valuation'),
        "home_odds_raw": match_core_details.get('home_odds_raw'),
        "away_odds_raw": match_core_details.get('away_odds_raw'),
        "draw_odds_raw": match_core_details.get('draw_odds_raw')
    }

    sent_task = _internal_fetch_sentiment_for_baseline_ds(
        ai_input_md.copy(), api_semaphore, sentiment_cache_instance,
        perplexity_api_key_val, ai_call_timeout_val
    )
    news_task = _internal_fetch_news_for_baseline_ds(
        ai_input_md.copy(), api_semaphore, news_cache_instance,
        perplexity_api_key_val, ai_call_timeout_val
    )
    sent_data_res, news_sum_raw = await asyncio.gather(sent_task, news_task, return_exceptions=True)

    cur_so_sent_h, cur_so_sent_a = "N/A", "N/A"
    ai_input_for_prediction = ai_input_md.copy()

    if isinstance(sent_data_res, dict) and not sent_data_res.get("error"):
        h_sent_dets = sent_data_res.get('home_sentiment_details', {})
        a_sent_dets = sent_data_res.get('away_sentiment_details', {})
        if h_sent_dets.get('score') is not None: cur_so_sent_h = f"{h_sent_dets['score']:.2f}"
        if a_sent_dets.get('score') is not None: cur_so_sent_a = f"{a_sent_dets['score']:.2f}"
        ai_input_for_prediction['home_sentiment_details'] = h_sent_dets
        ai_input_for_prediction['away_sentiment_details'] = a_sent_dets
    else:
        logger.warning(f"DS: Sentiment data issue for {match_id}: {sent_data_res}")
        ai_input_for_prediction['home_sentiment_details'] = {}
        ai_input_for_prediction['away_sentiment_details'] = {}

    key_news_sum = "News N/A"
    if isinstance(news_sum_raw, str) and not news_sum_raw.lower().startswith("error:"):
        key_news_sum = news_sum_raw
    elif isinstance(news_sum_raw, Exception):
        logger.warning(f"DS: News fetch ex {match_id}: {news_sum_raw}")

    pred_data_res = await _internal_get_perplexity_prediction_ds(
        ai_input_for_prediction, api_semaphore, prediction_cache_instance,
        perplexity_api_key_val, ai_call_timeout_val
    )
    cur_so_pred = "Prediction N/A"
    if isinstance(pred_data_res, dict) and not pred_data_res.get("error"):
        winner = pred_data_res.get('winner', 'N/A')
        conf = pred_data_res.get('confidence_score')
        score = pred_data_res.get('predicted_score', 'N/A')
        conf_str = f"({conf*100:.0f}%)" if conf is not None else ""
        cur_so_pred = f"{winner} {score} {conf_str}".strip()
    else:
        logger.warning(f"DS: Prediction data issue for {match_id}: {pred_data_res}")

    odds_parts = []
    home_odds_raw_val = match_core_details.get('home_odds_raw', 'N/A')
    home_odds_dec_val = match_core_details.get('home_odds', 'N/A')
    away_odds_raw_val = match_core_details.get('away_odds_raw', 'N/A')
    away_odds_dec_val = match_core_details.get('away_odds', 'N/A')
    draw_odds_raw_val = match_core_details.get('draw_odds_raw', 'N/A')
    draw_odds_dec_val = match_core_details.get('draw_odds', 'N/A')
    home_official_name = match_core_details.get('home_team_official_odds_name', ht_off)
    away_official_name = match_core_details.get('away_team_official_odds_name', at_off)

    if home_odds_raw_val != 'N/A' and home_odds_dec_val != 'N/A': odds_parts.append(f"H2H: {home_official_name} @{home_odds_raw_val} ({home_odds_dec_val} Dec)")
    if away_odds_raw_val != 'N/A' and away_odds_dec_val != 'N/A': odds_parts.append(f"{away_official_name} @{away_odds_raw_val} ({away_odds_dec_val} Dec)")
    if draw_odds_raw_val != 'N/A' and draw_odds_dec_val != 'N/A': odds_parts.append(f"Draw @{draw_odds_raw_val} ({draw_odds_dec_val} Dec)")

    home_spread_pts_val = match_core_details.get('home_spread_points', 'N/A')
    home_spread_odds_val = match_core_details.get('home_spread_odds_raw', 'N/A')
    if home_spread_pts_val != 'N/A' and home_spread_odds_val != 'N/A':
        odds_parts.append(f"Spread: {home_official_name} {home_spread_pts_val} @{home_spread_odds_val}")

    total_line_val = match_core_details.get('total_over_under_line', 'N/A')
    total_over_odds_val = match_core_details.get('total_over_odds_raw', 'N/A')
    total_under_odds_val = match_core_details.get('total_under_odds_raw', 'N/A')
    if total_line_val != 'N/A' and total_over_odds_val != 'N/A' and total_under_odds_val != 'N/A':
        odds_parts.append(f"Total: O/U {total_line_val} (Over @{total_over_odds_val}, Under @{total_under_odds_val})")
    final_odds_summary = ". ".join(odds_parts) + "." if odds_parts else "Odds N/A."

    baseline_out = {
        "match_title": f"{ht_off} vs. {at_off} ({sdisp_name} - {match_date})",
        "sport_key": sport_key,
        "team_a_name_official": ht_off,
        "team_b_name_official": at_off,
        "match_date": match_date,
        "odds_data_summary": final_odds_summary,
        "valuation_data_summary": f"{ht_off} ~${match_core_details.get('home_valuation', 0.0):.0f}M, {at_off} ~${match_core_details.get('away_valuation', 0.0):.0f}M.",
        "current_so_prediction_info": cur_so_pred,
        "current_so_sentiment_home_info": cur_so_sent_h,
        "current_so_sentiment_away_info": cur_so_sent_a,
        "key_news_summary_info": key_news_sum
    }

    logger.info(f"DS: Compiled baseline for {match_id} ({sport_key}).")
    full_match_details_cache[cache_key] = baseline_out
    return baseline_out