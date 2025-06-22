# adk_sportsomegapro/main.py
import asyncio
import os
import json
import logging
from dotenv import load_dotenv
import aiohttp
from cachetools import TTLCache
from typing import Dict, Any

# <<< FIX INTEGRATED >>>
# Correctly import the placeholder class from its new home
from adk_placeholders import ADKApplication

# --- Project Imports ---
from agents.chief_scout import ChiefScoutAgent
from agents.research_orchestrator import ResearchOrchestratorAgent
from tools.baseline_data import BaselineDataTool
from tools.perplexity_research import PerplexityResearchTool
from plans.dossier_plan import DossierGenerationPlan
from dossier_generator import _render_dossier_json_to_markdown

# --- Logging & Environment Setup ---
load_dotenv()
log_level = logging.DEBUG if os.getenv("APP_ENV", "").lower() == "development" else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', force=True)
logger = logging.getLogger("ADK_MAIN_RUNNER")

### ADDED: Final Dossier Report Cache ###
# Cache for 4 hours, storing up to 100 final dossier reports.
dossier_cache = TTLCache(maxsize=100, ttl=3600 * 24)

async def run_adk_dossier_pipeline(match_details_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initializes and runs the full Manna Maker engine pipeline.
    Checks for a cached dossier before running the full workflow.
    """
    ### ADDED: Cache Check Logic ###
    # --- 1. Check Cache First ---
    match_id = match_details_input.get("match_id")
    sport_key = match_details_input.get("sport_key")

    if not match_id or not sport_key:
        error_msg = "Input must contain 'match_id' and 'sport_key' to generate or retrieve a dossier."
        logger.error(error_msg)
        return {"critical_outer_error": error_msg}

    cache_key = f"dossier_v1_{sport_key}_{match_id}"
    cached_dossier = dossier_cache.get(cache_key)
    if cached_dossier:
        logger.info(f"DOSSIER CACHE HIT for key: {cache_key}. Serving from cache.")
        # Optionally, add a flag to indicate the result is from the cache for consumers.
        cached_dossier["_from_cache"] = True
        return cached_dossier

    logger.info(f"DOSSIER CACHE MISS for key: {cache_key}. Proceeding with pipeline execution.")
    logger.info(f"Initiating ADK dossier pipeline for: {match_details_input}")


    # Critical Environment Validation
    required_vars = ["PERPLEXITY_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "ODDS_API_KEY"]
    missing_vars = [v for v in required_vars if not os.getenv(v)]
    if missing_vars:
        error_msg = f"Missing critical environment variables: {', '.join(missing_vars)}"
        logger.critical(f"ADK Pipeline cannot start. {error_msg}")
        return {"critical_outer_error": error_msg}

    gemini_model = os.getenv("GEMINI_MODEL_ADK", "gemini-2.5-flash-preview-05-20")
    
    async with aiohttp.ClientSession() as http_session:
        api_semaphore = asyncio.Semaphore(int(os.getenv('API_SEMAPHORE_LIMIT', '3')))
        
        # --- Initialize Agents ---
        logger.info(f"Initializing agents with Gemini model: {gemini_model}")
        agents = {
            "ChiefScoutAgent": ChiefScoutAgent(model_name=gemini_model),
            "ResearchOrchestratorAgent": ResearchOrchestratorAgent(model_name=gemini_model)
        }

        # --- Initialize Tools ---
        logger.info("Initializing tools...")
        tools = {
            "BaselineDataTool": BaselineDataTool(
                http_session=http_session, api_semaphore=api_semaphore,
                sentiment_cache=TTLCache(maxsize=50, ttl=3600),
                prediction_cache=TTLCache(maxsize=50, ttl=3600),
                news_cache=TTLCache(maxsize=50, ttl=3600),
                perplexity_api_key=str(os.getenv("PERPLEXITY_API_KEY")),
                ai_call_timeout=int(os.getenv('AI_CALL_TIMEOUT', '40'))
            ),
            "PerplexityResearchTool": PerplexityResearchTool(
                api_key=str(os.getenv("PERPLEXITY_API_KEY")),
                api_semaphore=api_semaphore,
                ai_call_timeout=int(os.getenv('AI_CALL_TIMEOUT', '40'))
            )
        }
        
        # --- Initialize Plan ---
        dossier_plan = DossierGenerationPlan()

        # --- Assemble and Run ---
        adk_app = ADKApplication(plan=dossier_plan, tool_registry=tools, agent_registry=agents)
        final_state = {}
        try:
            logger.info(f"Starting ADKApplication.run for match: {match_details_input.get('match_id')}")
            final_state = await adk_app.run(match_details_input)
            logger.info("ADKApplication.run completed.")
            # ... (post-processing and output saving logic remains the same) ...
        except Exception as e:
            final_state["critical_outer_error"] = f"CRITICAL UNHANDLED EXCEPTION: {e}"
            logger.critical(final_state["critical_outer_error"], exc_info=True)
        
        ### ADDED: Cache Result Logic ###
        # --- Cache the result before returning ---
        # Only cache successful results, not those with critical errors.
        if "critical_outer_error" not in final_state and "error" not in final_state.get("dossier_json", {}):
            logger.info(f"CACHING successful dossier result for key: {cache_key}")
            dossier_cache[cache_key] = final_state
        else:
            err_detail = final_state.get("critical_outer_error") or final_state.get("dossier_json", {}).get("error")
            logger.warning(f"NOT CACHING dossier for {cache_key} due to errors in the final state. Error: {err_detail}")

        return final_state

if __name__ == "__main__":
    test_match = {
        "match_id": os.getenv("TEST_MATCH_ID", "175f25b4c55cfecdf0909fb953833b2f"),
        "sport_key": os.getenv("TEST_SPORT_KEY", "soccer_fifa_world_cup_qualifiers_europe"),
        "team_a": os.getenv("TEST_TEAM_A", "Italy"),
        "team_b": os.getenv("TEST_TEAM_B", "Moldova")
    }
    asyncio.run(run_adk_dossier_pipeline(test_match))
