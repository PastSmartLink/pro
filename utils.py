import os
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
# import requests # REMOVED
import aiohttp  # ADDED
import asyncio  # ADDED
from cachetools import TTLCache, cached

logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Add basic handler if none configured
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Static Data
SPORTS = {
    'soccer_epl': 'Premier League (EPL)', 'baseball_mlb': 'MLB', 'basketball_nba': 'NBA',
    'americanfootball_nfl': 'NFL', 'americanfootball_ncaaf': 'NCAAF',
    'soccer_uefa_champs_league': 'UEFA Champions League', 'icehockey_nhl': 'NHL', 'basketball_wnba': 'WNBA',
    'soccer_italy_serie_a': 'Serie A - Italy', 'soccer_spain_la_liga': 'La Liga - Spain',
    'soccer_germany_bundesliga': 'Bundesliga - Germany', 'soccer_france_ligue_one': 'Ligue 1 - France',
    'soccer_usa_mls': 'MLS - USA', 'cricket_ipl': 'Cricket - IPL', 'aussierules_afl': 'AFL',
    'soccer_netherlands_eredivisie': 'Eredivisie'
}
SPORTS_DISPLAY = SPORTS.copy()

TYPICAL_OFFSEASON_MONTHS = {
    'soccer_epl': [6, 7], 'americanfootball_nfl': [2, 3, 4, 5, 6, 7, 8],
    'soccer_uefa_champs_league': [6, 7, 8], 'soccer_italy_serie_a': [6, 7],
    'soccer_spain_la_liga': [6, 7], 'soccer_germany_bundesliga': [6, 7],
    'soccer_france_ligue_one': [6, 7], 'soccer_netherlands_eredivisie': [6, 7],
    'baseball_mlb': [11,12,1, 2], 'basketball_nba': [7, 8, 9], 'icehockey_nhl': [7, 8, 9],
    'basketball_wnba': [10, 11, 12, 1, 2, 3, 4],'americanfootball_ncaaf': [1, 2, 3, 4, 5, 6, 7, 8],
    'soccer_usa_mls': [11, 12, 1, 2], 'cricket_ipl': [], 'aussierules_afl': [10, 11, 12, 1, 2]
}

CLUB_DATA: Dict[str, Any] = {}
try:
    _CURR_DIR = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(_CURR_DIR, 'data', 'club_data_full.json')
    if os.path.exists(data_file_path):
        with open(data_file_path, 'r', encoding='utf-8') as f_club:
            CLUB_DATA = json.load(f_club)
        logger.info(f"Successfully loaded club_data_full.json from: {data_file_path}")
    else:
        logger.error(f"CRITICAL Error: club_data_full.json not found at {data_file_path}")
        CLUB_DATA = {"name_variations": {}, "valuations": {}} # Provide default empty structure
except Exception as e_club:
    logger.error(f"CRITICAL Error loading club_data_full.json: {e_club}", exc_info=True)
    CLUB_DATA = {"name_variations": {}, "valuations": {}} # Provide default empty structure


# Caches
odds_data_cache: Dict[str, List[Dict[str, Any]]] = {} # Sport_key -> List of game dicts
odds_cache_timestamps: Dict[str, datetime] = {}      # Sport_key -> Timestamp of last fetch
empty_sports_cache: Dict[str, bool] = {} # Tracks sports that returned empty & not offseason

ODDS_API_KEY = os.getenv('ODDS_API_KEY')
ODDS_API_URL_TEMPLATE = 'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/'
FUTURE_LIMIT_DAYS = int(os.environ.get('SCRIPT_FUTURE_LIMIT_DAYS_CONST', 7))


def is_likely_offseason(sport_key: str) -> bool:
    current_month = datetime.now(timezone.utc).month
    offseason_months = TYPICAL_OFFSEASON_MONTHS.get(sport_key, [])
    return bool(offseason_months and current_month in offseason_months)

def normalize_team_name_util(team_name: Optional[str], sport_key: str) -> str:
    if not isinstance(team_name, str) or not team_name.strip(): 
        return str(team_name) if team_name is not None else "" 
    if not CLUB_DATA or 'name_variations' not in CLUB_DATA: 
        return team_name
    sport_variations = CLUB_DATA.get('name_variations', {}).get(sport_key, {})
    return sport_variations.get(team_name, team_name)

@cached(TTLCache(maxsize=2048, ttl=3600*24*7)) 
def get_valuation_from_club_data_util(team_name_canonical: str, sport_key: str) -> float:
    if not team_name_canonical or not sport_key: return 0.0
    if not CLUB_DATA or 'valuations' not in CLUB_DATA: return 0.0
    val_str = str(CLUB_DATA.get('valuations', {}).get(sport_key, {}).get(team_name_canonical, "0.0"))
    try:
        cleaned_val_str = val_str.upper().replace('M', '').replace('B','').replace(',','').strip()
        if not cleaned_val_str: return 0.0
        if 'B' in val_str.upper(): 
            return float(cleaned_val_str) * 1000 
        return float(cleaned_val_str)
    except ValueError: 
        return 0.0

# RENAMED and REWRITTEN to be async with aiohttp
async def fetch_odds_from_api_async(sport_key: str, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    if not ODDS_API_KEY: 
        logger.error(f"Odds API key missing for {sport_key}. Cannot fetch odds.")
        return []
    
    bookmakers = 'draftkings,fanduel,betmgm,pointsbetus,caesars,betrivers' # Considered comma-separated
    params = {
        'apiKey': ODDS_API_KEY, 
        'regions': 'us', 
        'markets': 'h2h,spreads,totals',
        'dateFormat': 'iso', 
        'oddsFormat': 'american',
        'bookmakers': bookmakers
    }
    url = ODDS_API_URL_TEMPLATE.format(sport_key=sport_key)
    
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status() 
            data = await response.json()

            if not isinstance(data, list): 
                logger.error(f"Unexpected odds API response format for {sport_key}. Expected list, got {type(data)}.")
                return []

            now_utc = datetime.now(timezone.utc)
            future_limit_dt = now_utc + timedelta(days=FUTURE_LIMIT_DAYS)
            valid_matches = []
            
            for game in data:
                ts_str = game.get('commence_time')
                if not ts_str: 
                    logger.warning(f"Skipping game (ID: {game.get('id', 'Unknown')}) due to missing 'commence_time'.")
                    continue
                try:
                    comm_dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    if now_utc <= comm_dt < future_limit_dt:
                        valid_matches.append(game)
                except ValueError:
                    logger.warning(f"Invalid commence_time format for game ID {game.get('id')}: {ts_str}")
            
            if not valid_matches and not is_likely_offseason(sport_key):
                empty_sports_cache[sport_key] = True 
                logger.info(f"No upcoming matches found for {sport_key} via API (async). Marking as empty.")
            else:
                empty_sports_cache.pop(sport_key, None)
            return valid_matches

    except aiohttp.ClientError as e: 
        logger.error(f"Odds API HTTP error (aiohttp) for {sport_key}: {e}")
    except asyncio.TimeoutError:
        logger.error(f"Odds API request (aiohttp) timed out for {sport_key}")
    except json.JSONDecodeError as e_json:
        try:
            resp_text = await response.text() if 'response' in locals() and hasattr(response, 'text') else "N/A"
            logger.error(f"Odds API JSON decode error (aiohttp) for {sport_key}: {e_json}. Response text start: {resp_text[:200]}")
        except Exception as getTextErr:
            logger.error(f"Odds API JSON decode error (aiohttp) for {sport_key}: {e_json}, and failed to get response text: {getTextErr}")
    return []


# RENAMED and REWRITTEN to be async
async def get_cached_odds_async(sport_key: str, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Fetches odds from cache or API asynchronously using the provided aiohttp session.
    """
    now = datetime.now(timezone.utc)
    cached_data = odds_data_cache.get(sport_key)
    ts = odds_cache_timestamps.get(sport_key)

    is_offseason_val = is_likely_offseason(sport_key)
    is_empty_val = empty_sports_cache.get(sport_key, False)
    ttl_seconds = 3600 * 24 if is_offseason_val or is_empty_val else 3600 * 2 # 24h for off/empty, 2h otherwise

    if cached_data is not None and ts and (now - ts < timedelta(seconds=ttl_seconds)):
        logger.debug(f"CACHE HIT for odds (async): {sport_key}")
        return cached_data

    logger.info(f"CACHE MISS/STALE for odds (async): {sport_key}. Fetching new data.")
    new_data = await fetch_odds_from_api_async(sport_key, session)
    
    if new_data:
        odds_data_cache[sport_key] = new_data
        odds_cache_timestamps[sport_key] = now
        empty_sports_cache.pop(sport_key, None) # Clear empty flag if data received
        logger.info(f"Async: Successfully fetched and cached {len(new_data)} new odds for {sport_key}.")
    elif not new_data and not is_offseason_val: # Fetch failed or returned no data for an active season
        # Potentially clear old cache or keep it for a bit longer with an older timestamp?
        # For now, clearing it ensures we don't serve very stale data if API is temporarily down.
        odds_data_cache.pop(sport_key, None) 
        odds_cache_timestamps.pop(sport_key, None)
        empty_sports_cache[sport_key] = True # Mark as empty
        logger.warning(f"Async: Failed to fetch new odds or no games found for active sport {sport_key}. Cache updated accordingly.")
    elif is_offseason_val: # It's offseason, an empty list is expected.
        # Update cache with empty list and current timestamp to respect TTL
        odds_data_cache[sport_key] = [] 
        odds_cache_timestamps[sport_key] = now
        empty_sports_cache.pop(sport_key, None) # Not "empty" in the sense of missing data
        logger.info(f"Async: {sport_key} is likely in offseason. Cached empty odds list.")

    return new_data # new_data will be an empty list if fetch failed