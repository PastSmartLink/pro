# adk_sportsomegapro/tools/perplexity_research.py
from adk_placeholders import Tool
# ** FIX: Removed the incorrect import from dossier_generator to break the circular dependency. **
# The API call logic now lives directly inside this tool.
import httpx # A modern async http client, use whichever you had before (aiohttp, etc.)
import asyncio
import logging
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

# The endpoint for Perplexity AI's online models
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

    async def execute(self, params: Dict[str, Any]) -> str: # Returns string (finding or error message)
        query_string = params.get("query_string")
        if not query_string or not isinstance(query_string, str):
            logger.warning(f"{self.name}: Invalid or missing query_string.")
            return "Error: No valid query string provided to PerplexityResearchTool."
        
        logger.info(f"{self.name}: Executing research query: '{query_string[:100]}...'")

        # ** FIX: The logic to call the API is now correctly placed inside the tool's execute method. **
        # It is controlled by the semaphore to manage concurrency.
        async with self.api_semaphore:
            try:
                # Using httpx as an example for an async HTTP client
                async with httpx.AsyncClient(timeout=self.ai_call_timeout) as client:
                    payload = {
                        "model": "llama-3-sonar-large-32k-online", # Use the appropriate model
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
                    response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

                    response_json = response.json()
                    finding_text = response_json["choices"][0]["message"]["content"]

                if not finding_text:
                     logger.warning(f"{self.name}: Query '{query_string[:50]}...' returned an empty response from Perplexity.")
                     return f"Error: Perplexity research for '{query_string[:50]}...' yielded no result."
                
                logger.info(f"{self.name}: Successfully executed query '{query_string[:50]}...'.")
                return finding_text.strip()

            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                logger.error(f"{self.name}: HTTP error during Perplexity query: {e}. Body: {error_body}")
                return f"Error: Perplexity API returned status {e.response.status_code} for query '{query_string[:50]}...'"
            except httpx.TimeoutException:
                 logger.error(f"{self.name}: Timeout error after {self.ai_call_timeout}s on query '{query_string[:50]}...'.")
                 return f"Error: Perplexity API call timed out on query '{query_string[:50]}...'"
            except Exception as e:
                logger.error(f"{self.name}: Unhandled exception during Perplexity query execution for '{query_string[:50]}...': {e}", exc_info=True)
                return f"Error: Unhandled exception in {self.name} for query '{query_string[:50]}...': {type(e).__name__}"
