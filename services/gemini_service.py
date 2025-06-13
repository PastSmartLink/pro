# gemini_service.py
import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    Part,
    Content, 
    HarmCategory,
    HarmBlockThreshold,
    GenerationResponse,
    GenerationConfig
)
import os
import logging
import asyncio
import json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    retry_if_exception_type
)
from typing import Optional, List, Union, Any, Dict, cast
from dotenv import load_dotenv
from adk_prompt_manager import prompt_manager

load_dotenv()

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

RETRYABLE_GEMINI_EXCEPTIONS = (Exception,)

class GeminiService:
    AI_RESPONSE_ISSUE_FLAG = "Error: AI_RESPONSE_ISSUE"

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-05-20"):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        self.model: Optional[GenerativeModel] = None
        self.model_name_used: str = model_name

        if not self.project_id or not self.location:
            logger.error("CRITICAL FAILURE: GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION not set.")
            return

        try:
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if credentials_path and not os.path.exists(credentials_path):
                logger.error(f"CRITICAL FAILURE: GOOGLE_APPLICATION_CREDENTIALS path '{credentials_path}' does not exist.")
                return
            
            logger.info(f"Attempting vertexai.init with project='{self.project_id}', location='{self.location}'...")
            vertexai.init(project=self.project_id, location=self.location)
            
            system_instruction_single_string = prompt_manager.get_prompt('Master_Cognitive_Directive')
            logger.info("MASTER COGNITIVE DIRECTIVE SECURELY LOADED AS SYSTEM PROMPT.")
            logger.info(f"VERIFICATION SNIPPET: '{system_instruction_single_string[:100]}...'")
            
            logger.info(f"Attempting to load GenerativeModel: '{self.model_name_used}' with system instruction.")
            self.model = GenerativeModel(
                self.model_name_used,
                system_instruction=system_instruction_single_string 
            )
            logger.info(f"GeminiService initialized successfully: model='{self.model_name_used}'.")

        except Exception as e: 
            logger.error(f"Error during GeminiService initialization for '{self.model_name_used}': {e}", exc_info=True)
            self.model = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
        reraise=True, 
        before_sleep=before_sleep_log(logger, logging.WARNING, exc_info=True)
    )
    async def call_model_async(
        self, 
        prompt_text: str, 
        generation_config_override: Optional[Union[GenerationConfig, Dict[str, Any]]] = None
    ) -> str:
        if not self.model:
            raise RuntimeError("GeminiService model not initialized.")

        contents_for_call: List[Content] = [Content(role="user", parts=[Part.from_text(prompt_text)])]

        current_generation_config_dict = {
            "max_output_tokens": 8192, 
            "temperature": 0.7,       
            "top_p": 0.95,            
        }
        if generation_config_override:
            if isinstance(generation_config_override, dict):
                current_generation_config_dict.update(generation_config_override)
            elif isinstance(generation_config_override, GenerationConfig):
                current_generation_config_dict = {
                    "max_output_tokens": getattr(generation_config_override, "max_output_tokens", None),
                    "temperature": getattr(generation_config_override, "temperature", None),
                    "top_p": getattr(generation_config_override, "top_p", None),
                    "top_k": getattr(generation_config_override, "top_k", None),
                    "response_mime_type": getattr(generation_config_override, "response_mime_type", None),
                }
                current_generation_config_dict = {k: v for k, v in current_generation_config_dict.items() if v is not None}

        safety_settings_dict = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

        try:
            api_response_object = await self.model.generate_content_async(
                contents=contents_for_call,
                generation_config=current_generation_config_dict,
                safety_settings=safety_settings_dict,
                stream=False 
            )
            response = cast(GenerationResponse, api_response_object)

            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                full_text = "".join(
                    part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text is not None
                ).strip()
                if full_text: 
                    return full_text
            
            finish_reason_obj = response.candidates[0].finish_reason if (response.candidates and len(response.candidates) > 0) else None
            finish_reason_str = finish_reason_obj.name if finish_reason_obj else "UNKNOWN_NO_CANDIDATES_OR_EMPTY"
            
            block_reason_details = ""
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_details = (
                    f" Prompt Feedback Block Reason: {response.prompt_feedback.block_reason.name if response.prompt_feedback.block_reason else 'N/A'}. "
                    f"Message: '{response.prompt_feedback.block_reason_message or 'N/A'}'."
                )
            
            safety_details = ""
            if response.candidates and len(response.candidates) > 0 and hasattr(response.candidates[0], 'safety_ratings') and response.candidates[0].safety_ratings:
                 safety_ratings_text = ", ".join([f"{rating.category.name}: {rating.probability.name}" for rating in response.candidates[0].safety_ratings])
                 safety_details = f" Safety Ratings: [{safety_ratings_text}]."

            error_message = (
                f"Gemini Warning for '{self.model_name_used}': No substantive content/generation stopped. "
                f"Finish Reason: {finish_reason_str}.{block_reason_details}{safety_details}"
            )
            logger.warning(error_message)
            return f"{GeminiService.AI_RESPONSE_ISSUE_FLAG} ({error_message})" 

        except Exception as e: 
            logger.error(f"Exception during Gemini API call to '{self.model_name_used}': {e}", exc_info=True)
            raise

async def main_test_gemini():
    print("Attempting to initialize GeminiService for testing...")
    service = GeminiService() 
    
    if service.model: 
        test_json_prompt = "Output a simple JSON object: {\"name\": \"Test Name\", \"value\": 123}"
        json_config = {"temperature": 0.2, "response_mime_type": "application/json"}
        
        print(f"\nSending test JSON prompt to Gemini (model: '{service.model_name_used}') with low temp:")
        try:
            response_text_json = await service.call_model_async(test_json_prompt, generation_config_override=json_config)
            print("\n--- Gemini Response (JSON Prompt) ---")
            print(response_text_json)
            print("--- End of Response ---")
            if not response_text_json.startswith(GeminiService.AI_RESPONSE_ISSUE_FLAG):
                try:
                    parsed = json.loads(response_text_json)
                    print(f"Successfully parsed JSON: {parsed}")
                except json.JSONDecodeError as je:
                    print(f"Failed to parse JSON from response: {je}")
        except Exception as e:
            print(f"\n--- ERROR DURING GEMINI JSON CALL: {type(e).__name__} - {e} ---")

        test_narrative_prompt = "Describe a sunset over a mountain range in 3 sentences."
        print(f"\nSending test narrative prompt to Gemini (model: '{service.model_name_used}') with default temp:")
        try:
            response_text_narrative = await service.call_model_async(test_narrative_prompt)
            print("\n--- Gemini Response (Narrative Prompt) ---")
            print(response_text_narrative)
            print("--- End of Response ---")
        except Exception as e:
            print(f"\n--- ERROR DURING GEMINI NARRATIVE CALL: {type(e).__name__} - {e} ---")
    else:
        print("\nCRITICAL: Failed to initialize GeminiService for testing.")

if __name__ == '__main__':
    asyncio.run(main_test_gemini())