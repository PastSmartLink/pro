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
        
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()

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
        # <<< FIX 1: Corrected model name and added stream=False >>>
        payload = {"model": "sonar-small-32k-online", "messages": correction_prompt, "stream": False}
        
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
            return {"error": "API key not configured"} if expect_json else "Error: API key not configured"

        url = "https://api.perplexity.ai/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # <<< FIX 2: Added stream=False >>>
        payload = {"model": model, "messages": messages, "stream": False}
        
        logger.info(f"Sending ASYNC request to PPLX. Model: {model}. Expect JSON: {expect_json}.")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    raw_response = await response.text()
                    response.raise_for_status()
                    
                    data = json.loads(raw_response)
                    content_str = str(data.get('choices', [{}])[0].get('message', {}).get('content', ''))

                    if not expect_json:
                        return content_str

                    processed_text = PerplexityAIService._preprocess_json_text(content_str)
                    if not processed_text:
                         return {"error": "Empty content after preprocessing"}
                    try:
                        parsed_data = json.loads(processed_text, strict=False)
                        logger.info("Successfully parsed JSON from Perplexity API.")
                        return parsed_data
                    except json.JSONDecodeError as e_json:
                        logger.error(f"Initial JSON parse failed. Raw: {content_str[:200]}")
                        try:
                            return await PerplexityAIService._attempt_ai_correction(processed_text, api_key, session)
                        except Exception as e_correction:
                            logger.critical(f"AI self-correction FAILED: {e_correction}. Original error: {e_json}")
                            return {"error": f"Invalid JSON from AI and correction failed."}

            except Exception as e:
                logger.error(f"Error in ask_async: {e}", exc_info=True)
                return {"error": str(e)} if expect_json else f"Error: {str(e)}"
