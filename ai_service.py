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
        """
        Cleans the raw text from the AI to make it more JSON-parsable.
        Removes markdown fences and attempts to isolate the primary JSON object.
        """
        if text is None:
            return ""
        # Remove markdown code block delimiters more robustly
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # Attempt to find the main JSON object/array if there's extraneous text
        json_match = re.search(r'(\{([^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\[([^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        else:
            logger.debug(f"Could not find a clear JSON object/array in pre-processing text: '{text[:100]}...'")

        text = re.sub(r'(:\s*)\+\s*(\d)', r'\1\2', text)
        text = re.sub(r'([\[,]\s*)\+\s*(\d)', r'\1\2', text)

        return text.strip()

    @staticmethod
    async def _attempt_ai_correction(
        broken_text: str,
        api_key: str,
        session: aiohttp.ClientSession
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        An internal method to ask a fast AI model to fix broken JSON syntax.
        This is a single, non-retrying attempt to provide a self-healing capability.
        """
        logger.warning(f"Initial JSON parse failed. Attempting AI-powered self-correction...")
        correction_prompt = [
            {'role': 'system', 'content': 'You are a JSON syntax correction utility. The user provides broken or malformed JSON text. Your only job is to fix the syntax (e.g., missing commas, brackets, quotes, unescaped characters) and return ONLY the perfectly valid JSON. Do not add any commentary or explanation.'},
            {'role': 'user', 'content': broken_text}
        ]
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Use a fast, capable model for syntax correction.
        payload = {"model": "llama-3-sonar-small-32k-online", "messages": correction_prompt, "stream": False}
        
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            correction_data = await response.json()
            
            raw_corrected_text = correction_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not raw_corrected_text:
                raise ValueError("AI self-correction returned empty content.")
            
            # Preprocess and parse the now-corrected text
            processed_correction = PerplexityAIService._preprocess_json_text(str(raw_corrected_text))
            final_parsed_data = json.loads(processed_correction)
            logger.info("AI self-correction successful! Successfully parsed the corrected JSON.")
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
        model: str = "llama-3-sonar-small-32k-online",
        api_key: Optional[str] = None,
        timeout: int = 40, # Increased default timeout for larger models
        expect_json: bool = True
    ) -> Union[Dict[str, Any], List[Any], str]:
        if not api_key:
            logger.error("API key must be provided for PerplexityAIService.")
            return {"error": "API key not configured"} if expect_json else "Error: API key not configured"
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"model": model, "messages": messages, "stream": False}
        
        logger.info(f"Sending ASYNC request to Perplexity API. Model: {model}. Expect JSON: {expect_json}. Messages: {len(messages)}")
        raw_response_text_for_logging = "No response text captured."
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    raw_response_text_for_logging = await response.text()
                    logger.debug(f"Perplexity API ({model}) raw response status: {response.status}, text (start): {raw_response_text_for_logging[:250]}...")
                    
                    response.raise_for_status()
                    
                    if 'application/json' not in response.headers.get('Content-Type', '').lower():
                        logger.error(f"Perplexity API ({model}) did not return JSON. Content-Type: {response.headers.get('Content-Type')}. Response: {raw_response_text_for_logging[:500]}")
                        if expect_json:
                            raise ValueError("API response not JSON when JSON was expected.")
                        return raw_response_text_for_logging

                    result_data = json.loads(raw_response_text_for_logging)
                                        
                    choices = result_data.get('choices')
                    if not choices or not isinstance(choices, list) or len(choices) == 0:
                        raise ValueError("Malformed API response: no valid 'choices'.")
                    
                    message_obj = choices[0].get('message', {})
                    message_content_raw = message_obj.get('content')
                    if message_content_raw is None:
                        raise ValueError("Malformed API response: no 'content' in message.")

                    message_content_str = str(message_content_raw).strip()

                    if expect_json:
                        processed_text = PerplexityAIService._preprocess_json_text(message_content_str)
                        if not processed_text:
                            logger.warning(f"Empty content after preprocessing for JSON. Original: '{message_content_str[:100]}...'")
                            return {"error": "Empty content from AI after preprocessing"}
                        try:
                            # --- Primary Parse Attempt ---
                            # strict=False is kept as a first line of defense for minor control character issues
                            parsed_data = json.loads(processed_text, strict=False) 
                            if not isinstance(parsed_data, (dict, list)):
                                logger.error(f"Parsed JSON is not a dictionary or list. Type: {type(parsed_data)}.")
                                return {"error": "Parsed content is not valid JSON structure (dict/list)"}
                            logger.info(f"Successfully parsed JSON from Perplexity API. Model: {model}")
                            return parsed_data
                        except json.JSONDecodeError as e_json:
                            logger.error(f"Initial JSON parse failed: {e_json}. Processed text for parsing: >>>{processed_text}<<<")
                            # --- AI SELF-CORRECTION ATTEMPT ---
                            try:
                                return await PerplexityAIService._attempt_ai_correction(processed_text, api_key, session)
                            except Exception as e_correction:
                                logger.critical(f"AI self-correction FAILED: {e_correction}. This may indicate a persistent issue. Returning original parse error.")
                                return {"error": f"Invalid JSON from AI and correction failed: {str(e_json)}"}
                    else: # Expecting plain text
                        logger.info(f"Returning plain text data from Perplexity API. Model: {model}")
                        if message_content_str.startswith("```") and message_content_str.endswith("```"):
                            cleaned_text = re.sub(r'^```[a-zA-Z]*\n', '', message_content_str)
                            cleaned_text = re.sub(r'\n```$', '', cleaned_text)
                            message_content_str = cleaned_text.strip()
                        return message_content_str

            except ValueError as e_val:
                logger.error(f"Data processing error in ask_async for model {model}: {e_val}.")
                return {"error": f"AI response processing error: {str(e_val)}"} if expect_json else f"Error: AI response processing error"
            except RetryError as e_retry:
                last_exception = e_retry.last_attempt.exception()
                logger.error(f"API call failed after all retries for model {model}. Last exception: {last_exception}")
                return {"error": "AI service unavailable after multiple retries"} if expect_json else "Error: AI service unavailable"
            except Exception as e_gen:
                logger.exception(f"Unexpected non-retryable error in ask_async for model {model}. API Response Text: '{raw_response_text_for_logging}'")
                return {"error": f"Unexpected system error: {type(e_gen).__name__}"} if expect_json else f"Unexpected system error"
