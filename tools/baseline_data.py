# adk_sportsomegapro/tools/baseline_data.py
from adk_placeholders import Tool
from data_services import get_full_match_details_for_dossier_baseline
from cachetools import TTLCache
import aiohttp
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BaselineDataTool(Tool):
    def __init__(
        self,
        http_session: aiohttp.ClientSession,
        api_semaphore: asyncio.Semaphore,
        sentiment_cache: TTLCache,
        prediction_cache: TTLCache,
        news_cache: TTLCache,
        perplexity_api_key: str,
        ai_call_timeout: int
    ):
        super().__init__(name="SportsMatchBaselineDataTool", description="Fetches comprehensive baseline data for a sports match.")
        self.http_session = http_session
        self.api_semaphore = api_semaphore
        self.sentiment_cache = sentiment_cache
        self.prediction_cache = prediction_cache
        self.news_cache = news_cache
        self.perplexity_api_key = perplexity_api_key
        self.ai_call_timeout = ai_call_timeout
        logger.info(f"{self.name} initialized.")

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "match_id": {"type": "string", "description": "Unique identifier for the match."},
                        "sport_key": {"type": "string", "description": "Key identifying the sport (e.g., 'icehockey_nhl')."},
                        "team_a": {"type": "string", "description": "Display name of Team A (home team)."},
                        "team_b": {"type": "string", "description": "Display name of Team B (away team)."}
                    },
                    "required": ["match_id", "sport_key", "team_a", "team_b"]
                }
            }
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        match_id = params.get("match_id")
        sport_key = params.get("sport_key")
        team_a_input = params.get("team_a")
        team_b_input = params.get("team_b")

        if not all(isinstance(x, str) and x for x in [match_id, sport_key, team_a_input, team_b_input]):
            err_msg = f"{self.name} Error: Missing or invalid required parameters: match_id, sport_key, team_a, team_b."
            logger.error(err_msg)
            return {"error": err_msg}
        
        match_id = str(match_id)
        sport_key = str(sport_key)
        team_a_input = str(team_a_input)
        team_b_input = str(team_b_input)

        logger.info(f"{self.name}: Fetching baseline for {match_id}, {sport_key}, {team_a_input} vs {team_b_input}")
        try:
            result = await get_full_match_details_for_dossier_baseline(
                match_id=match_id,
                sport_key=sport_key,
                team_a_name_input=team_a_input, 
                team_b_name_input=team_b_input,
                http_session=self.http_session,
                api_semaphore=self.api_semaphore,
                sentiment_cache_instance=self.sentiment_cache,
                prediction_cache_instance=self.prediction_cache,
                news_cache_instance=self.news_cache,
                perplexity_api_key_val=self.perplexity_api_key,
                ai_call_timeout_val=self.ai_call_timeout
            )
            if not isinstance(result, dict):
                logger.error(f"{self.name}: get_full_match_details did not return a dict. Got: {type(result)}")
                return {"error": f"Internal error: Baseline data function returned unexpected type {type(result)}."}

            # Post-process result to handle missing fields
            missing_fields = []
            if not result.get("team_a_name_official"):
                missing_fields.append("team_a_name_official")
                result["team_a_name_official"] = team_a_input
            if not result.get("team_b_name_official"):
                missing_fields.append("team_b_name_official")
                result["team_b_name_official"] = team_b_input
            if not result.get("match_date"):
                missing_fields.append("match_date")
                result["match_date"] = "TBD"
                logger.info(f"{self.name}: Set placeholder match_date='TBD' for {match_id}")
            if not result.get("odds_data_summary"):
                missing_fields.append("odds_data_summary")
                result["odds_data_summary"] = "N/A"
            if not result.get("key_news_summary_info"):
                missing_fields.append("key_news_summary_info")
                result["key_news_summary_info"] = "No news available"

            if missing_fields:
                warn_msg = f"Partial baseline data for {match_id}. Missing: {missing_fields}"
                logger.warning(f"{self.name}: {warn_msg}")
                result["warning"] = warn_msg

            logger.info(f"{self.name}: Successfully fetched baseline for {match_id}.")
            return result
        except Exception as e:
            logger.error(f"{self.name}: Exception during baseline data fetch for {match_id}: {e}", exc_info=True)
            return {"error": f"Unhandled exception in {self.name}: {type(e).__name__} - {e}"}
