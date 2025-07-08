# FILE: render-main/ai_service.py

import aiohttp
import asyncio
import json
import logging
import re
from typing import Dict, Any, Union, List, Optional, TypedDict, Literal
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    RetryError,
    before_sleep_log,
    retry_if_exception_type,
)
import time

logger = logging.getLogger(__name__)

# --- Type Definitions for strong typing ---
class ChatMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str

# Define exceptions that should trigger a retry attempt for API calls.
RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientResponseError,
    aiohttp.ClientConnectionError,
    asyncio.TimeoutError,
)

# --- Utility Functions for Text Processing ---
def _strip_markdown_fences(text: str) -> str:
    """Removes markdown fences (e.g., ```json) from text, returning the inner content."""
    if not text:
        return ""
    # This regex handles multiline fenced code blocks and extracts content.
    pattern = r"^\s*```(?:json)?\n(.*?)\n```\s*$"
    cleaned_text = re.sub(pattern, r"\1", text, flags=re.DOTALL | re.MULTILINE)
    # Fallback to remove any lingering triple backticks.
    return cleaned_text.replace("```", "").strip()

def _extract_json_block(text: str) -> str:
    """Finds and returns the first valid-looking JSON object or array from a string."""
    pattern = r"(\{(?:[^{}]|(?:\{[^{}]*\}))*\}|\[(?:[^\[\]]|\[(?:[^\[\]]*\])*\])*\])"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(0).strip() if match else ""

# --- Service Class Definitions ---
class PerplexityAIService:
    @staticmethod
    def _preprocess_json_text(text: str) -> str:
        """Cleans and isolates a JSON block from raw LLM text."""
        stripped = _strip_markdown_fences(text)
        return _extract_json_block(stripped)

    @staticmethod
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5))
    async def _attempt_ai_correction(
        broken_text: str, api_key: str, session: aiohttp.ClientSession
    ) -> Union[Dict, List]:
        """Sends malformed JSON back to the Perplexity API for self-correction."""
        logger.warning("Attempting AI self-correction for malformed JSON...")
        correction_prompt: List[ChatMessage] = [
            {'role': 'system', 'content': 'You are a JSON syntax correction utility. The user provides broken JSON. Return ONLY the perfectly valid JSON. If it is impossible to fix, return an empty object {}.'},
            {'role': 'user', 'content': broken_text}
        ]
        
        payload = {"model": "sonar-pro", "messages": correction_prompt, "stream": False}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        try:
            async with session.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '{}')
                return json.loads(PerplexityAIService._preprocess_json_text(content))
        except Exception as e:
            logger.error(f"AI self-correction failed: {e}")
            return {}

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING, exc_info=True)
    )
    async def ask_async(
        messages: List[ChatMessage], model: str, api_key: Optional[str], timeout: int, expect_json: bool
    ) -> Union[Dict[str, Any], List[Any], str]:
        
        if not api_key:
            return {"error": "API key not provided to PerplexityAIService."} if expect_json else "Error: API Key missing."

        url = "https://api.perplexity.ai/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "stream": False}
        
        start_time = time.time()
        logger.info(f"Perplexity ASK_ASYNC → model={model} | expect_json={expect_json}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    raw_text = await response.text()
                    response.raise_for_status()
                    data = json.loads(raw_text)
                    
                    # <<< PRIMARY FIX FOR THE AttributeError >>>
                    # 'choices' is a LIST. Access the first element [0].
                    choices_list = data.get('choices')
                    if not isinstance(choices_list, list) or not choices_list:
                        raise ValueError("Perplexity API response did not contain a 'choices' list.")
                    
                    content_str = str(choices_list[0].get('message', {}).get('content', ''))
                    
                    if not expect_json:
                        return content_str
                    
                    processed = PerplexityAIService._preprocess_json_text(content_str)
                    if not processed:
                        return {"error": "Content was empty after preprocessing", "raw_content": content_str}
                        
                    try:
                        return json.loads(processed)
                    except json.JSONDecodeError:
                        return await PerplexityAIService._attempt_ai_correction(processed, api_key, session)
            
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Perplexity API call failed after {duration:.2f}s: {e.__class__.__name__} - {e}", exc_info=True)
                err_msg = f"API Error: {e.__class__.__name__}: {e}"
                return {"error": err_msg} if expect_json else err_msg