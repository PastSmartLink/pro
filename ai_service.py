# ai_service.py (Corrected for the pro-main backend service)

import aiohttp
import asyncio
import logging
import json
import re
from typing import Dict, Any, Union, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError, before_sleep_log, retry_if_exception_type

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientResponseError,
    aiohttp.ClientConnectionError,
    asyncio.TimeoutError,
)

class PerplexityAIService:
    @staticmethod
    def _preprocess_json_text(text: str) -> str:
        if not text:
            return ""
        
        # Remove markdown code fences (```json ... ```)
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # Extract the first valid-looking JSON object or array from the text
        json_match = re.search(r'(\{([^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\[([^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        else:
            logger.debug(f"Could not find a clear JSON block in text: '{text[:100]}...'")
            return ""
        return text.strip()

    @staticmethod
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING, exc_info=True)
    )
    async def _attempt_ai_correction(
        broken_text: str,
        api_key: str,
        session: aiohttp.ClientSession
    ) -> Union[Dict[str, Any], List[Any]]:
        logger.warning("Initial JSON parse failed. Attempting AI-powered self-correction...")
        correction_prompt = [
            {'role': 'system', 'content': 'You are a JSON syntax correction utility. The user provides broken or malformed JSON text. Your only job is to fix the syntax and return ONLY the perfectly valid JSON. Do not add any commentary or explanation. If the input is too broken to fix, return an empty JSON object {}.'},
            {'role': 'user', 'content': broken_text}
        ]
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # <<< FIX #1: Added "stream": False >>>
        # This is critical. By default, the API may use streaming.
        # Our code reads the response at once, so we must request a non-streaming response.
        payload = {"model": "sonar-pro", "messages": correction_prompt, "stream": False}
        
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            correction_data = await response.json()
            
            raw_corrected_text = correction_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            processed_correction = PerplexityAIService._preprocess_json_text(str(raw_corrected_text))
            
            if not processed_correction:
                logger.error("AI self-correction returned empty or un-processable content.")
                return {}
            
            final_parsed_data = json.loads(processed_correction)
            logger.info("AI self-correction successful!")
            return final_parsed_data

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=12),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING, exc_info=True)
    )
    async def ask_async(
        messages: List[Dict[str, str]],
        model: str,
        api_key: Optional[str] = None,
        timeout: int = 40,
        expect_json: bool = True
    ) -> Union[Dict[str, Any], List[Any], str]:
        if not api_key:
            error_message = "Error: API key not configured for PerplexityAIService"
            return {"error": error_message} if expect_json else error_message

        url = "https://api.perplexity.ai/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # <<< FIX #2: Added "stream": False >>>
        # This is the primary fix. It ensures the API returns a complete JSON object
        # instead of a streaming response, which prevents the 400 Bad Request error.
        payload = {"model": model, "messages": messages, "stream": False}
        
        # Log the payload for easier debugging, but be mindful of sensitive data in production.
        # logger.debug(f"Sending request to PPLX with payload: {json.dumps(payload)}")
        logger.info(f"Sending ASYNC request to PPLX. Model: {model}. Expect JSON: {expect_json}.")
        
        # Use a single session for retries within this call
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    raw_response = await response.text()
                    
                    # This will now raise for 4xx/5xx errors, including the 400 we were seeing.
                    response.raise_for_status()
                    
                    # Proceed with processing the successful response
                    data = json.loads(raw_response)
                    content_str = str(data.get('choices', [{}])[0].get('message', {}).get('content', ''))

                    if not expect_json:
                        return content_str

                    processed_text = PerplexityAIService._preprocess_json_text(content_str)
                    if not processed_text:
                         return {"error": "Empty content after preprocessing", "raw_content": content_str}
                    try:
                        parsed_data = json.loads(processed_text, strict=False)
                        logger.info("Successfully parsed JSON from Perplexity API.")
                        return parsed_data
                    except json.JSONDecodeError as e_json:
                        logger.error(f"Initial JSON parse failed. Raw content snippet: {content_str[:200]}...")
                        try:
                            # Pass the existing session to the correction function
                            return await PerplexityAIService._attempt_ai_correction(processed_text, api_key, session)
                        except Exception as e_correction:
                            logger.critical(f"AI self-correction FAILED: {e_correction}. Original error: {e_json}")
                            return {"error": "Invalid JSON from AI and correction failed.", "details": str(e_correction)}

            except (aiohttp.ClientResponseError, asyncio.TimeoutError, Exception) as e:
                # This block catches errors during the request itself or from raise_for_status()
                # The tenacity retry logic will handle re-attempts. If all retries fail,
                # the exception will be re-raised and caught here for final error packaging.
                logger.error(f"Error in ask_async after retries for model {model}: {e}", exc_info=True)
                error_detail = f"Error communicating with Perplexity API: {str(e)}"
                return {"error": error_detail} if expect_json else error_detail
