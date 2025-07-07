# adk_sportsomegapro/tools/perplexity_research.py - FINAL PRODUCTION VERSION
import httpx
import asyncio
import logging
from typing import Dict, Any, Union

from adk_placeholders import Tool

logger = logging.getLogger(__name__)
PERPLEXITY_API_ENDPOINT = "https://api.perplexity.ai/chat/completions"

class PerplexityResearchTool(Tool):
    def __init__(self, api_key: str, api_semaphore: asyncio.Semaphore, ai_call_timeout: int):
        super().__init__(name="TargetedPerplexityResearchTool", description="Executes a targeted research query using Perplexity AI.")
        self.api_key = api_key
        self.api_semaphore = api_semaphore
        self.ai_call_timeout = ai_call_timeout
        logger.info(f"{self.name} initialized.")

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_string": {"type": "string", "description": "The exact query to be sent to Perplexity AI."}
                    },
                    "required": ["query_string"]
                }
            }
        }

    async def execute(self, params: Dict[str, Any]) -> str:
        query_string = params.get("query_string")
        if not query_string or not isinstance(query_string, str):
            logger.warning(f"{self.name}: Invalid or missing query_string.")
            return "Error: No valid query string provided to PerplexityResearchTool."
        
        logger.info(f"{self.name}: Executing research query: '{query_string[:100]}...'")

        async with self.api_semaphore:
            try:
                async with httpx.AsyncClient(timeout=self.ai_call_timeout) as client:
                    # ** FIX: Set the model to "sonar-pro" as per your working configuration. **
                    payload = {
                        "model": "sonar-pro",
                        "messages": [
                            {"role": "system", "content": "You are an expert AI research assistant. Provide a concise, factual, and direct answer to the user's query."},
                            {"role": "user", "content": query_string}
                        ]
                    }
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    response = await client.post(PERPLEXITY_API_ENDPOINT, json=payload, headers=headers)
                    response.raise_for_status()

                    response_json = response.json()
                    finding_text = response_json["choices"][0]["message"]["content"]

                if not finding_text:
                     logger.warning(f"{self.name}: Query '{query_string[:50]}...' returned an empty response.")
                     return f"Error: Perplexity research for '{query_string[:50]}...' yielded no result."
                
                logger.info(f"{self.name}: Successfully executed query '{query_string[:50]}...'.")
                return finding_text.strip()

            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                logger.error(f"{self.name}: HTTP error during Perplexity query: {e}. Body: {error_body}")
                return f"Error: Perplexity API returned status {e.response.status_code}."
            except httpx.TimeoutException:
                 logger.error(f"{self.name}: Timeout on query '{query_string[:50]}...'.")
                 return f"Error: Perplexity API call timed out."
            except Exception as e:
                logger.error(f"{self.name}: Unhandled exception during Perplexity query: {e}", exc_info=True)
                return f"Error: Unhandled exception in {self.name}: {type(e).__name__}"
