import aiohttp
import asyncio
import logging
import json
import re
from typing import Dict, Any, Union, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientResponseError,
    aiohttp.ClientConnectionError,
    asyncio.TimeoutError,
)

class PerplexityAIService:
    VALID_MODELS = ["sonar-small-online", "sonar-medium-online"]  # List of supported models

    @staticmethod
    def _preprocess_json_text(text: str) -> str:
        """
        Cleans the raw text from the AI to make it more JSON-parsable.
        Removes markdown fences and attempts to isolate the primary JSON object.
        """
        if not text or text.isspace():
            return ""
        # Remove markdown code block delimiters
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # Attempt to find the main JSON object/array
        json_match = re.search(r'(\{([^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\[([^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
        else:
            logger.debug(f"Could not find a clear JSON object/array in text: '{text[:100]}...'")
            return ""

        # Fix common JSON issues
        text = re.sub(r'(:\s*)\+\s*(\d)', r'\1\2', text)
        text = re.sub(r'([\[,]\s*)\+\s*(\d)', r'\1\2', text)

        return text.strip()

    @staticmethod
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.WARNING, exc_info=True)
    )
    async def _attempt_ai_correction(
        broken_text: str,
        api_key: str,
        session: aiohttp.ClientSession
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        An internal method to ask a fast AI model to fix broken JSON syntax.
        """
        logger.warning("Initial JSON parse failed. Attempting AI-powered self-correction...")
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
        payload = {"model": "sonar-small-online", "messages": correction_prompt}
        
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
            response.raise_for_status()
            correction_data = await response.json()
            
            raw_corrected_text = correction_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if not raw_corrected_text:
                logger.error("AI self-correction returned empty content.")
                raise ValueError("AI self-correction returned empty content.")
            
            processed_correction = PerplexityAIService._preprocess_json_text(raw_corrected_text)
            if not processed_correction:
                logger.error("Processed correction text is empty after preprocessing.")
                raise ValueError("Processed correction text is empty.")
            
            try:
                final_parsed_data = json.loads(processed_correction)
                logger.info("AI self-correction successful!")
                return final_parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse corrected JSON: {e}. Corrected text: '{processed_correction[:100]}...'")
                raise ValueError("Failed to parse AI-corrected JSON.")

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
        model: str = "sonar-medium-online",  # Updated default model
        api_key: Optional[str] = None,
        timeout: int = 40,
        expect_json: bool = True
    ) -> Union[Dict[str, Any], List[Any], str]:
        if not api_key:
            logger.error("API key must be provided for PerplexityAIService.")
            return {"error": "API key not configured"} if expect_json else "Error: API key not configured"
        
        # Validate model
        if model not in PerplexityAIService.VALID_MODELS:
            logger.warning(f"Invalid model: {model}. Falling back to sonar-medium-online")
            model = "sonar-medium-online"

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"model": model, "messages": messages}
        
        logger.info(f"Sending ASYNC request to Perplexity API. Model: {model}. Expect JSON: {expect_json}. Messages: {len(messages)}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    raw_response_text = await response.text()
                    logger.debug(f"Perplexity API ({model}) raw response status: {response.status}, text: '{raw_response_text[:250]}...'")
                    
                    response.raise_for_status()
                    
                    if 'application/json' not in response.headers.get('Content-Type', '').lower():
                        logger.error(f"Perplexity API ({model}) did not return JSON. Content-Type: {response.headers.get('Content-Type')}. Response: '{raw_response_text[:500]}...'")
                        if expect_json:
                            raise ValueError("API response not JSON when JSON was expected.")
                        return raw_response_text

                    result_data = json.loads(raw_response_text)
                    choices = result_data.get('choices', [])
                    if not choices or not isinstance(choices, list) or len(choices) == 0:
                        logger.error(f"Malformed API response: no valid 'choices'. Response: '{raw_response_text[:500]}...'")
                        raise ValueError("Malformed API response: no valid 'choices'.")
                    
                    message_obj = choices[0].get('message', {})
                    message_content_raw = message_obj.get('content')
                    if message_content_raw is None:
                        logger.error(f"Malformed API response: no 'content' in message. Response: '{raw_response_text[:500]}...'")
                        raise ValueError("Malformed API response: no 'content' in message.")

                    message_content_str = str(message_content_raw).strip()

                    if expect_json:
                        processed_text = PerplexityAIService._preprocess_json_text(message_content_str)
                        if not processed_text:
                            logger.warning(f"Empty content after preprocessing. Original: '{message_content_str[:100]}...'")
                            return {"error": "Empty content from AI after preprocessing"}
                        try:
                            parsed_data = json.loads(processed_text, strict=False)
                            if not isinstance(parsed_data, (dict, list)):
                                logger.error(f"Parsed JSON is not a dictionary or list. Type: {type(parsed_data)}. Text: '{processed_text[:100]}...'")
                                return {"error": "Parsed content is not valid JSON structure (dict/list)"}
                            logger.info(f"Successfully parsed JSON from Perplexity API. Model: {model}")
                            return parsed_data
                        except json.JSONDecodeError as e_json:
                            logger.error(f"Initial JSON parse failed: {e_json}. Processed text: '{processed_text[:200]}...'")
                            try:
                                return await PerplexityAIService._attempt_ai_correction(processed_text, api_key, session)
                            except Exception as e_correction:
                                logger.critical(f"AI self-correction failed: {e_correction}. Original error: {e_json}. Processed text: '{processed_text[:200]}...'")
                                return {"error": f"Invalid JSON from AI and correction failed: {str(e_json)}"}
                    else:
                        logger.info(f"Returning plain text from Perplexity API. Model: {model}")
                        if message_content_str.startswith("```") and message_content_str.endswith("```"):
                            cleaned_text = re.sub(r'^```[a-zA-Z]*\n', '', message_content_str)
                            cleaned_text = re.sub(r'\n```$', '', cleaned_text)
                            message_content_str = cleaned_text.strip()
                        return message_content_str

            except aiohttp.ClientResponseError as e:
                if e.status == 400 and "invalid_model" in raw_response_text.lower():
                    logger.warning(f"Model {model} invalid. Falling back to sonar-small-online")
                    payload["model"] = "sonar-small-online"
                    async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as fallback_response:
                        raw_response_text = await fallback_response.text()
                        fallback_response.raise_for_status()
                        result_data = json.loads(raw_response_text)
                        choices = result_data.get('choices', [])
                        if not choices or not isinstance(choices, list) or len(choices) == 0:
                            logger.error(f"Malformed fallback response: no valid 'choices'. Response: '{raw_response_text[:500]}...'")
                            raise ValueError("Malformed fallback response: no valid 'choices'.")
                        message_obj = choices[0].get('message', {})
                        message_content_raw = message_obj.get('content')
                        if message_content_raw is None:
                            logger.error(f"Malformed fallback response: no 'content'. Response: '{raw_response_text[:500]}...'")
                            raise ValueError("Malformed fallback response: no 'content'.")
                        message_content_str = str(message_content_raw).strip()
                        if expect_json:
                            processed_text = PerplexityAIService._preprocess_json_text(message_content_str)
                            if not processed_text:
                                logger.warning(f"Empty content after preprocessing in fallback. Original: '{message_content_str[:100]}...'")
                                return {"error": "Empty content from AI after preprocessing in fallback"}
                            try:
                                parsed_data = json.loads(processed_text, strict=False)
                                if not isinstance(parsed_data, (dict, list)):
                                    logger.error(f"Parsed JSON in fallback is not a dict/list. Type: {type(parsed_data)}. Text: '{processed_text[:100]}...'")
                                    return {"error": "Parsed content in fallback is not valid JSON structure (dict/list)"}
                                logger.info(f"Successfully parsed JSON from Perplexity API in fallback. Model: sonar-small-online")
                                return parsed_data
                            except json.JSONDecodeError as e_json:
                                logger.error(f"Initial JSON parse failed in fallback: {e_json}. Processed text: '{processed_text[:200]}...'")
                                try:
                                    return await PerplexityAIService._attempt_ai_correction(processed_text, api_key, session)
                                except Exception as e_correction:
                                    logger.critical(f"AI self-correction failed in fallback: {e_correction}. Original error: {e_json}. Processed text: '{processed_text[:200]}...'")
                                    return {"error": f"Invalid JSON from AI and correction failed in fallback: {str(e_json)}"}
                        else:
                            logger.info(f"Returning plain text from Perplexity API in fallback. Model: sonar-small-online")
                            if message_content_str.startswith("```") and message_content_str.endswith("```"):
                                cleaned_text = re.sub(r'^```[a-zA-Z]*\n', '', message_content_str)
                                cleaned_text = re.sub(r'\n```$', '', cleaned_text)
                                message_content_str = cleaned_text.strip()
                            return message_content_str
                else:
                    logger.error(f"Client response error in ask_async for model {model}: {e}. Response: '{raw_response_text[:500]}...'")
                    raise
            except ValueError as e_val:
                logger.error(f"Data processing error in ask_async for model {model}: {e_val}. Response: '{raw_response_text[:500]}...'")
                return {"error": f"AI response processing error: {str(e_val)}"} if expect_json else f"Error: AI response processing error"
            except Exception as e_gen:
                logger.error(f"Unexpected error in ask_async for model {model}: {e_gen}. Response: '{raw_response_text[:500]}...'")
                return {"error": f"Unexpected system error: {type(e_gen).__name__}"} if expect_json else f"Unexpected system error"
