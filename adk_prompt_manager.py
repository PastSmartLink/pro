import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class ADKPromptManager:
    _instance = None
    _is_initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ADKPromptManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, prefix: str = "CSMP"):
        if self._is_initialized:
            return
            
        self.prompts: Dict[str, str] = {}
        self.prefix = prefix
        self._load_prompts_from_environment()
        self._is_initialized = True
        logger.info(f"ADKPromptManager Initialized. Loaded {len(self.prompts)} prompts with robust key generation.")

    def _normalize_key(self, key_str: str) -> str:
        """A robust function to normalize keys from env vars or lookup names."""
        # This function safely removes one prefix and one suffix if they exist.
        
        normalized = key_str
        prefix_to_remove = self.prefix + "_"
        suffix_to_remove = "_PROMPT"
        
        if normalized.startswith(prefix_to_remove):
            normalized = normalized[len(prefix_to_remove):]
            
        # Keep removing suffix as long as it exists (handles typos like _PROMPT_PROMPT)
        while normalized.endswith(suffix_to_remove):
            normalized = normalized[:-len(suffix_to_remove)]
            
        return normalized.lower()

    def _load_prompts_from_environment(self):
        """Loads prompts from environment variables using robust key normalization."""
        loaded_count = 0
        for env_var, value in os.environ.items():
            if env_var.startswith(self.prefix + "_") and env_var.endswith("_PROMPT"):
                key = self._normalize_key(env_var)
                if key:
                    self.prompts[key] = value
                    loaded_count += 1
        
        if loaded_count == 0:
            logger.warning("ADKPromptManager: No CSMP prompts found in environment variables.")

    def get_prompt(self, name: str) -> str:
        """
        Retrieves a prompt by its name. The name is normalized for lookup
        to match the way keys are generated from environment variables.
        """
        lookup_key = self._normalize_key(name)
        prompt = self.prompts.get(lookup_key)
        
        if not prompt:
            error_msg = f"CRITICAL PROMPT MISSING: Prompt '{name}' (normalized to '{lookup_key}') not found by ADKPromptManager."
            logger.critical(error_msg)
            logger.debug(f"Available ADK keys: {list(self.prompts.keys())}")
            raise ValueError(error_msg)
        return prompt

# Instantiate a single, global prompt manager for the entire application.
prompt_manager = ADKPromptManager()
