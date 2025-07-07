# adk_sportsomegapro/adk_service_api.py
import asyncio
import os
import uuid
import logging
import json
from typing import Dict, Any, Optional

import redis
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from main import run_adk_dossier_pipeline

# --- Environment & Logging Setup ---
load_dotenv()
api_log_level_setting = os.getenv("API_LOG_LEVEL", "INFO").upper()
numeric_api_log_level = getattr(logging, api_log_level_setting, logging.INFO)
logging.basicConfig(
    level=numeric_api_log_level,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - FastAPI - %(message)s',
    force=True
)
logger = logging.getLogger("ADK_Service_API")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="SPORTSΩmega PRO ADK Dossier Service",
    description="API for generating in-depth sports match dossiers via the Manna Maker Engine.",
    version="0.1.0"
)

# --- SHARED CACHE SETUP (Uses Redis) ---
try:
    redis_url = os.environ['REDIS_URL']
    # decode_responses=True is crucial for getting strings instead of bytes from Redis.
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    logger.info("Successfully connected to SHARED Redis instance for task state management.")
    TASK_TTL_SECONDS = 3600 * 6  # 6-hour expiry for task results.
except Exception as e:
    logger.critical(f"CRITICAL STARTUP FAILURE: Could not connect to Redis. REDIS_URL must be set and valid. Error: {e}")
    redis_client = None

# --- Pydantic Models for API validation ---
class GenerateDossierRequest(BaseModel):
    match_id: str = Field(..., description="Unique identifier for the match.")
    sport_key: str = Field(..., description="Sport key (e.g., 'basketball_nba').")
    team_a: str = Field(..., description="Name of Team A.")
    team_b: str = Field(..., description="Name of Team B.")

class GenerateDossierResponse(BaseModel):
    task_id: str
    status: str = "QUEUED"
    message: str

class DossierStatusResponse(BaseModel):
    task_id: str
    status: str
    progress_message: Optional[str] = None
    match_title: Optional[str] = None
    dossier_json: Optional[Dict[str, Any]] = None
    error_detail: Optional[str] = None

# --- Redis Helper Function ---
def set_task_status_in_redis(task_id: str, status_data: Dict[str, Any]):
    if redis_client:
        try:
            redis_client.set(task_id, json.dumps(status_data), ex=TASK_TTL_SECONDS)
        except Exception as e:
            logger.error(f"REDIS_ERROR: Failed to set task status for {task_id}: {e}", exc_info=True)

# --- Background Task to run the AGI pipeline ---
async def run_pipeline_background(task_id: str, match_details: Dict[str, Any]):
    logger.info(f"Task ID {task_id}: Starting background ADK pipeline for match: {match_details.get('match_id')}")
    set_task_status_in_redis(task_id, {"status": "PROCESSING", "progress_message": "Manna Maker Engine Initializing..."})
    
    try:
        pipeline_final_state = await run_adk_dossier_pipeline(match_details)
        if not isinstance(pipeline_final_state, dict):
            raise TypeError(f"ADK Pipeline returned non-dict object: {type(pipeline_final_state)}")

        dossier_content = pipeline_final_state.get("dossier_json")
        error_detail_from_pipeline = None

        if isinstance(dossier_content, dict) and dossier_content.get("error"):
            error_detail_from_pipeline = dossier_content.get("error")
        elif pipeline_final_state.get("critical_outer_error"):
            error_detail_from_pipeline = pipeline_final_state.get("critical_outer_error")

        if not error_detail_from_pipeline:
            logger.info(f"Task ID {task_id}: ADK Pipeline COMPLETED successfully.")
            set_task_status_in_redis(task_id, {
                "status": "COMPLETED", 
                "result": dossier_content
            })
        else:
            logger.error(f"Task ID {task_id}: ADK Pipeline FAILED. Error: {error_detail_from_pipeline}")
            set_task_status_in_redis(task_id, {"status": "FAILED", "error_detail": str(error_detail_from_pipeline)})

    except Exception as e:
        logger.critical(f"Task ID {task_id}: CRITICAL UNHANDLED EXCEPTION in background pipeline: {e}", exc_info=True)
        set_task_status_in_redis(task_id, {"status": "FAILED", "error_detail": f"Critical service error: {type(e).__name__}"})

# --- API Endpoints ---
@app.post("/v1/generate-dossier", response_model=GenerateDossierResponse, status_code=202)
async def trigger_dossier_generation(request_data: GenerateDossierRequest, background_tasks: BackgroundTasks):
    task_id = f"adk_task_{uuid.uuid4().hex}"
    logger.info(f"Received /v1/generate-dossier request. Assigning Task ID: {task_id}")
    set_task_status_in_redis(task_id, {"status": "QUEUED", "progress_message": "Task accepted and queued."})
    background_tasks.add_task(run_pipeline_background, task_id, request_data.dict())
    return GenerateDossierResponse(task_id=task_id, message="Dossier generation initiated.")

@app.get("/v1/dossier-status/{task_id}", response_model=DossierStatusResponse)
async def get_dossier_status(task_id: str):
    if not redis_client:
        raise HTTPException(status_code=503, detail="Cache service (Redis) is not connected.")

    task_json = redis_client.get(task_id)

    if not task_json:
        logger.warning(f"Task ID {task_id} not found in SHARED Redis cache for status check.")
        raise HTTPException(status_code=404, detail="Task ID not found, may have expired or never existed.")

    task_info = json.loads(task_json)
    
    # Adapt to the simple data structure we are now setting in Redis
    return DossierStatusResponse(
        task_id=task_id,
        status=task_info.get("status", "UNKNOWN"),
        progress_message=task_info.get("progress_message"),
        match_title=task_info.get("result", {}).get("match_title") if task_info.get("result") else None,
        dossier_json=task_info.get("result"),
        error_detail=task_info.get("error_detail")
    )

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "SPORTSΩmega ADK Dossier Service is running."}

@app.head("/", include_in_schema=False)
async def root_head():
    return JSONResponse(status_code=200, content={})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join("static", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")

# Add the rest of the static file routes if you have them, e.g.,
# @app.get("/favicon-16x16.png", ...)

# --- Uvicorn entrypoint (for direct running) ---
if __name__ == "__main__":
    import uvicorn
    service_port = int(os.getenv("ADK_SERVICE_PORT", "8001"))
    logger.info(f"Starting ADK Service API on http://0.0.0.0:{service_port}")
 
    required_vars = ["PERPLEXITY_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "ODDS_API_KEY", "REDIS_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.critical(f"CRITICAL STARTUP FAILURE: Missing essential environment variables: {', '.join(missing_vars)}")
    elif redis_client is None:
         logger.critical(f"CRITICAL STARTUP FAILURE: Redis client could not be initialized. Check connection details.")
    else:
        gac_path_startup = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not os.path.exists(gac_path_startup):
            logger.critical(f"CRITICAL STARTUP FAILURE: GOOGLE_APPLICATION_CREDENTIALS path '{gac_path_startup}' is invalid.")
        else:
            uvicorn.run("adk_service_api:app", host="0.0.0.0", port=service_port, reload=True, log_level=api_log_level_setting.lower())
