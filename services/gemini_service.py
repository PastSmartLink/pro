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
# Use the root-level adk_prompt_manager
from adk_prompt_manager import prompt_manager 

load_dotenv()
logger = logging.getLogger(__name__)

RETRYABLE_GEMINI_EXCEPTIONS = (Exception,)

class GeminiService:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model: Optional[GenerativeModel] = None

        if not self.project_id or not self.location:
            logger.critical("FATAL: GeminiService initialization failed. GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION env vars are not set.")
            return

        try:
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path or not os.path.exists(credentials_path):
                logger.critical(f"FATAL: GOOGLE_APPLICATION_CREDENTIALS path is not set or invalid: {credentials_path}")
                return

            vertexai.init(project=self.project_id, location=self.location)
            
            # <<< PRIMARY FIX for ValueError >>>
            # Call get_prompt with the base key name 'MASTER_COGNITIVE_DIRECTIVE_PROMPT'.
            # The prompt manager automatically handles adding prefixes/suffixes.
            system_instruction = prompt_manager.get_prompt('MASTER_COGNITIVE_DIRECTIVE_PROMPT')
            
            self.model = GenerativeModel(model_name, system_instruction=[system_instruction])
            logger.info(f"GeminiService initialized successfully for model '{model_name}'.")

        except ValueError as ve:
            # This catches the specific error when a prompt is not found.
            logger.critical(f"FATAL: A required prompt for GeminiService initialization is missing. Check your .env file or environment variables. Error: {ve}", exc_info=True)
            self.model = None # Ensure the model is None so checks for it will fail correctly.
        except Exception as e:
            logger.critical(f"A fatal, unexpected error occurred during GeminiService initialization: {e}", exc_info=True)
            self.model = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.5, min=2, max=10))
    async def call_model_async(
        self, prompt_text: str, generation_config_override: Optional[Dict] = None
    ) -> str:
        if not self.model:
            raise RuntimeError("GeminiService model is not initialized. Please review startup logs for fatal initialization errors.")
        
        # Default configuration, can be overridden by the call.
        config = { "max_output_tokens": 8192, "temperature": 0.7, **(generation_config_override or {}) }
        
        # Configure safety settings to be non-blocking to prevent content filtering issues.
        safety_settings = { category: HarmBlockThreshold.BLOCK_NONE for category in HarmCategory }

        try:
            response = await self.model.generate_content_async(
                [prompt_text],
                generation_config=GenerationConfig(**config),
                safety_settings=safety_settings
            )
            return response.text
        except Exception as e:
            logger.error(f"An exception occurred during the Gemini API call: {e}", exc_info=True)
            raise # Re-raise for Tenacity to handle retry logic.