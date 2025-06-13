# adk_sportsomegapro/adk_service_api.py
import asyncio
import os
import uuid
import logging
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Query
from fastapi.responses import JSONResponse, FileResponse  # Use FastAPI's FileResponse for serving files
from pydantic import BaseModel, Field  # For request/response validation
from cachetools import TTLCache 
from dotenv import load_dotenv  # Ensure .env is loaded for this service too

# --- Project Specific Imports ---
# This assumes main.py and other modules are in the python path or PYTHONPATH is set
# when running uvicorn, or you structure your project as a package.
# For simplicity if running uvicorn directly in adk_sportsomegapro dir:
from main import run_adk_dossier_pipeline 

# --- Load Environment Variables for this API service ---
load_dotenv()

# --- Logging Setup for FastAPI Service ---
# Consistent with your main.py, but can be separate if needed
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

# --- In-Memory Task Store (using TTLCache for simplicity with auto-expiration) ---
# Key: task_id (str), Value: Dict[str, Any] -> {"status": str, "progress_message": Optional[str], "result": Optional[Dict], "error_detail": Optional[str]}
TASK_RESULTS_CACHE: TTLCache = TTLCache(maxsize=200, ttl=3600 * 6)  # Cache tasks for 6 hours

# --- Pydantic Models for Request/Response Typing/Validation ---
class GenerateDossierRequest(BaseModel):
    match_id: str = Field(..., description="Unique identifier for the match.")
    sport_key: str = Field(..., description="Sport key (e.g., 'basketball_nba').")
    team_a: str = Field(..., description="Name of Team A (typically home team).")
    team_b: str = Field(..., description="Name of Team B (typically away team).")
    # We could add priority, specific model overrides, etc., later

class GenerateDossierResponse(BaseModel):
    task_id: str
    status: str = "QUEUED"  # Initial status
    message: str

class DossierStatusResponse(BaseModel):
    task_id: str
    status: str  # e.g., "QUEUED", "PROCESSING", "COMPLETED", "FAILED"
    progress_message: Optional[str] = None
    match_title: Optional[str] = None  # Populate this when COMPLETED from dossier_json
    dossier_json: Optional[Dict[str, Any]] = None  # The actual dossier if status is "COMPLETED"
    error_detail: Optional[str] = None

# --- Helper: Background Task to Run the ADK Pipeline ---
async def run_pipeline_background(task_id: str, match_details: Dict[str, Any]):
    logger.info(f"Task ID {task_id}: Starting background ADK pipeline for match: {match_details.get('match_id')}")
    TASK_RESULTS_CACHE[task_id] = {"status": "PROCESSING", "progress_message": "Manna Maker Engine Initializing..."}
 
    try:
        # `run_adk_dossier_pipeline` is your main function from main.py
        # It's expected to return the full final_state dictionary
        pipeline_final_state = await run_adk_dossier_pipeline(match_details)

        if not isinstance(pipeline_final_state, dict):
            logger.error(f"Task ID {task_id}: ADK Pipeline returned non-dict: {type(pipeline_final_state)}")
            TASK_RESULTS_CACHE[task_id] = {"status": "FAILED", "error_detail": "ADK Pipeline returned unexpected data type."}
            return

        dossier_content = pipeline_final_state.get("dossier_json")  # Extract the actual dossier
        plan_log = pipeline_final_state.get("plan_execution_log", [])  # Get execution log

        if isinstance(dossier_content, dict) and not dossier_content.get("error"):
            logger.info(f"Task ID {task_id}: ADK Pipeline COMPLETED successfully for {match_details.get('match_id')}.")
            TASK_RESULTS_CACHE[task_id] = {
                "status": "COMPLETED", 
                "result": dossier_content,  # Store the dossier_json here
                "match_title": dossier_content.get("match_title", "N/A"),
                "plan_execution_log_summary": [log["message"] for log in plan_log if isinstance(log, dict) and log.get("severity") == "INFO"][-5:]  # last 5 info messages
            }
        else:
            error_detail_from_pipeline = "Unknown error in dossier generation"
            if isinstance(dossier_content, dict) and dossier_content.get("error"):
                error_detail_from_pipeline = dossier_content.get("error")
            elif pipeline_final_state.get("critical_outer_error"):
                error_detail_from_pipeline = pipeline_final_state.get("critical_outer_error")

            logger.error(f"Task ID {task_id}: ADK Pipeline FAILED for {match_details.get('match_id')}. Error: {error_detail_from_pipeline}")
            TASK_RESULTS_CACHE[task_id] = {
                "status": "FAILED", 
                "error_detail": str(error_detail_from_pipeline),
                "plan_execution_log_errors": [log for log in plan_log if isinstance(log, dict) and log.get("severity","INFO") != "INFO"]  # Filter for non-INFO
            }

    except Exception as e:
        logger.critical(f"Task ID {task_id}: CRITICAL UNHANDLED EXCEPTION in background pipeline runner for {match_details.get('match_id')}: {e}", exc_info=True)
        TASK_RESULTS_CACHE[task_id] = {"status": "FAILED", "error_detail": f"Critical service error: {type(e).__name__} - {e}"}

# --- API Endpoints ---
@app.post("/v1/generate-dossier", response_model=GenerateDossierResponse, status_code=202)
async def trigger_dossier_generation(
    request_data: GenerateDossierRequest,
    background_tasks: BackgroundTasks
):
    """
    Initiates the generation of an Ωmega PRO Scouting Dossier.
    This is an asynchronous operation. Poll the status endpoint with the returned task_id.
    """
    task_id = f"adk_task_{uuid.uuid4().hex}"
    logger.info(f"Received /v1/generate-dossier request for match ID: {request_data.match_id}. Assigning Task ID: {task_id}")

    # Prepare input for your ADK pipeline function
    match_details_for_pipeline = {
        "match_id": request_data.match_id,
        "sport_key": request_data.sport_key,
        "team_a": request_data.team_a,  # These names will be used by data_services -> get_full_match_details if needed for initial label
        "team_b": request_data.team_b
    }
 
    TASK_RESULTS_CACHE[task_id] = {"status": "QUEUED", "progress_message": "Task accepted and queued for processing."}
 
    # Add the long-running pipeline execution as a background task
    background_tasks.add_task(run_pipeline_background, task_id, match_details_for_pipeline)
 
    return GenerateDossierResponse(
        task_id=task_id,
        message="PRO Dossier generation process initiated. Poll status endpoint for updates."
    )

@app.get("/v1/dossier-status/{task_id}", response_model=DossierStatusResponse)
async def get_dossier_status(task_id: str):
    """
    Retrieves the status and result of a dossier generation task.
    """
    logger.debug(f"Received /v1/dossier-status request for Task ID: {task_id}")
    task_info = TASK_RESULTS_CACHE.get(task_id)

    if not task_info:
        logger.warning(f"Task ID {task_id} not found in cache for status check.")
        raise HTTPException(status_code=404, detail="Task ID not found or expired.")

    # Prepare response based on task_info structure
    response_data = {
        "task_id": task_id,
        "status": task_info.get("status", "UNKNOWN"),
        "progress_message": task_info.get("progress_message"),  # Might be None
        "match_title": task_info.get("match_title"),          # Might be None initially
        "dossier_json": task_info.get("result"),             # This is `dossier_content` from run_pipeline_background if COMPLETED
        "error_detail": task_info.get("error_detail")        # Present if FAILED
    }
 
    return DossierStatusResponse(**response_data)

@app.get("/", include_in_schema=False)
async def root():
    """
    Simple health check / root endpoint.
    Supports GET for basic access.
    """
    return {"message": "SPORTSΩmega ADK Dossier Service is running."}

@app.head("/", include_in_schema=False)
async def root_head():
    """
    Handle HEAD requests for Render health checks.
    """
    return JSONResponse(status_code=200, content={})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """
    Serve favicon.ico from the static directory.
    """
    favicon_path = os.path.join("static", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Favicon.ico not found in static directory.")
        raise HTTPException(status_code=404, detail="Favicon not found")

# --- Additional Static Asset Routes (Optional) ---
@app.get("/favicon-16x16.png", include_in_schema=False)
async def favicon_16x16():
    """
    Serve favicon-16x16.png from the static directory.
    """
    favicon_path = os.path.join("static", "favicon-16x16.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Favicon-16x16.png not found in static directory.")
        raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/favicon-32x32.png", include_in_schema=False)
async def favicon_32x32():
    """
    Serve favicon-32x32.png from the static directory.
    """
    favicon_path = os.path.join("static", "favicon-32x32.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Favicon-32x32.png not found in static directory.")
        raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon():
    """
    Serve apple-touch-icon.png from the static directory.
    """
    favicon_path = os.path.join("static", "apple-touch-icon.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Apple-touch-icon.png not found in static directory.")
        raise HTTPException(status_code=404, detail="Apple touch icon not found")

@app.get("/android-chrome-192x192.png", include_in_schema=False)
async def android_chrome_192():
    """
    Serve android-chrome-192x192.png from the static directory.
    """
    favicon_path = os.path.join("static", "android-chrome-192x192.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Android-chrome-192x192.png not found in static directory.")
        raise HTTPException(status_code=404, detail="Android chrome icon not found")

@app.get("/android-chrome-512x512.png", include_in_schema=False)
async def android_chrome_512():
    """
    Serve android-chrome-512x512.png from the static directory.
    """
    favicon_path = os.path.join("static", "android-chrome-512x512.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Android-chrome-512x512.png not found in static directory.")
        raise HTTPException(status_code=404, detail="Android chrome icon not found")

@app.get("/site.webmanifest", include_in_schema=False)
async def site_webmanifest():
    """
    Serve site.webmanifest from the static directory.
    """
    favicon_path = os.path.join("static", "site.webmanifest")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    else:
        logger.warning("Site.webmanifest not found in static directory.")
        raise HTTPException(status_code=404, detail="Site webmanifest not found")

# --- Uvicorn entrypoint (for direct running, e.g., python adk_service_api.py) ---
if __name__ == "__main__":
    import uvicorn
    # Get port from environment or default to 8001
    service_port = int(os.getenv("ADK_SERVICE_PORT", "8001"))
    logger.info(f"Starting ADK Service API on http://0.0.0.0:{service_port}")
 
    # Critical check for environment variables before starting
    required_for_pipeline = ["PERPLEXITY_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "ODDS_API_KEY"]
    missing_critical_vars = [var for var in required_for_pipeline if not os.getenv(var)]
    if missing_critical_vars:
        logger.critical(f"CRITICAL STARTUP FAILURE: Missing essential environment variables for the ADK pipeline: {', '.join(missing_critical_vars)}. The ADK service cannot function correctly. Please set these variables.")
    else:
        gac_path_startup = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not gac_path_startup or not os.path.exists(gac_path_startup):
            logger.critical(f"CRITICAL STARTUP FAILURE: GOOGLE_APPLICATION_CREDENTIALS path '{gac_path_startup}' is invalid. ADK service will not function correctly.")

    uvicorn.run("adk_service_api:app", host="0.0.0.0", port=service_port, reload=True, log_level=api_log_level_setting.lower())