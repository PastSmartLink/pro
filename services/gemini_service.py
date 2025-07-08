# FILE: render-main/services/gemini_service.py

import vertexai
from vertexai.generative_models import (
    GenerativeModel, Part, Content, HarmCategory,
    HarmBlockThreshold, GenerationResponse, GenerationConfig
)
import os
import logging
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type
from typing import Optional, List, Union, Any, Dict, cast
from dotenv import load_dotenv
# Ensure the correct prompt manager is imported from the root level of your project
from adk_prompt_manager import prompt_manager 

load_dotenv()
logger = logging.getLogger(__name__)

RETRYABLE_GEMINI_EXCEPTIONS = (Exception,) # Broad for resilience, can be narrowed down

class GeminiService:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model: Optional[GenerativeModel] = None

        if not self.project_id or not self.location:
            logger.critical("FATAL: GeminiService cannot initialize. GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION not set.")
            return

        try:
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path or not os.path.exists(credentials_path):
                logger.critical(f"FATAL: GOOGLE_APPLICATION_CREDENTIALS path is invalid or not set: {credentials_path}")
                return

            vertexai.init(project=self.project_id, location=self.location)
            
            # This is the PRIMARY FIX for the ValueError.
            # The prompt manager expects the base name of the prompt.
            system_instruction = prompt_manager.get_prompt('MASTER_COGNITIVE_DIRECTIVE_PROMPT')
            
            self.model = GenerativeModel(model_name, system_instruction=[system_instruction])
            logger.info(f"GeminiService initialized successfully for model '{model_name}'.")

        except ValueError as ve:
            logger.critical(f"FATAL: A required prompt is missing for GeminiService initialization. Error: {ve}", exc_info=True)
            self.model = None # Ensure model is None if initialization fails.
        except Exception as e:
            logger.critical(f"An unexpected fatal error occurred during GeminiService initialization: {e}", exc_info=True)
            self.model = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.5, min=2, max=10))
    async def call_model_async(
        self, prompt_text: str, generation_config_override: Optional[Dict] = None
    ) -> str:
        if not self.model:
            raise RuntimeError("GeminiService model is not initialized. Review startup logs for fatal errors.")
        
        config = { "max_output_tokens": 8192, "temperature": 0.7, **(generation_config_override or {}) }
        
        safety_settings = { category: HarmBlockThreshold.BLOCK_NONE for category in HarmCategory }

        try:
            response = await self.model.generate_content_async(
                [prompt_text],
                generation_config=GenerationConfig(**config),
                safety_settings=safety_settings
            )
            return response.text
        except Exception as e:
            logger.error(f"Exception during Gemini API call: {e}", exc_info=True)
            raise # Re-raise for tenacity to handle retries