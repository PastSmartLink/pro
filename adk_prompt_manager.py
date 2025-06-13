# adk_prompt_manager.py
import os
import logging
from dotenv import load_dotenv
from typing import Dict

# Load environment variables from .env file at the module level
load_dotenv()
logger = logging.getLogger(__name__)

class PromptManager:
    """A singleton class to securely manage loading of proprietary prompts from environment variables."""
    _instance = None
    _is_initialized = False

    def __new__(cls, prefix: str = "CSMP") -> 'PromptManager':
        if cls._instance is None:
            cls._instance = super(PromptManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, prefix: str = "CSMP"):
        if self._is_initialized:
            return
        self.prefix = prefix
        self.prompts: Dict[str, str] = {}
        self._is_initialized = True
        logger.info(f"PromptManager initialized for prefix '{self.prefix}'. IP is secure.")

    def get_prompt(self, stage_name: str) -> str:
        """Retrieves a prompt by its logical stage name (e.g., 'stage_4_supergrok_inquiry')."""
        env_var_name = f"{self.prefix}_{stage_name.upper()}_PROMPT"
        
        if env_var_name in self.prompts:
            return self.prompts[env_var_name]
        
        prompt_content = os.getenv(env_var_name)
        if not prompt_content or not prompt_content.strip():
            error_msg = f"CRITICAL IP MISSING: Environment variable '{env_var_name}' is not set or empty."
            logger.critical(error_msg)
            raise ValueError(error_msg)
        
        self.prompts[env_var_name] = prompt_content
        logger.debug(f"Successfully loaded prompt for '{env_var_name}'.")
        return prompt_content

# Create a single, globally accessible instance of the PromptManager.
prompt_manager = PromptManager(prefix="CSMP")