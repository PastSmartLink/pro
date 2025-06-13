# adk_sportsomegapro/adk_utils.py
import re
import json
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

def extract_json_robustly(
    text_from_llm: str,
    expect_list: bool = False,
    context_for_logging: str = "LLM Response"
) -> Optional[Union[Dict[str, Any], List[Any]]]:
    if not isinstance(text_from_llm, str) or not text_from_llm.strip():
        logger.warning(f"extract_json_robustly ({context_for_logging}): Received empty or non-string input.")
        return None
    text = text_from_llm
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    if not text:
        logger.warning(f"extract_json_robustly ({context_for_logging}): Text became empty after stripping markdown.")
        return None
    
    primary_match_regex = r'(\[([^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\])' if expect_list else r'(\{([^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})'
    json_str_to_parse = text
    primary_match = re.search(primary_match_regex, text, re.DOTALL)
    
    if primary_match:
        json_str_to_parse = primary_match.group(0)
    else:
        fallback_match_regex = r'(\{([^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})' if expect_list else r'(\[([^\[\]]|\[(?:[^\[\]]|\[[^\[\]]*\])*\])*\])'
        fallback_match = re.search(fallback_match_regex, text, re.DOTALL)
        if fallback_match:
            json_str_to_parse = fallback_match.group(0)
        else:
            logger.debug(f"extract_json_robustly ({context_for_logging}): No clear JSON structure found via regex. Attempting to parse the full stripped text.")

    try:
        parsed_data = json.loads(json_str_to_parse)
        
        if expect_list and not isinstance(parsed_data, list):
            if isinstance(parsed_data, dict) and len(parsed_data) == 1 and isinstance(list(parsed_data.values())[0], list):
                return list(parsed_data.values())[0]
            logger.warning(f"extract_json_robustly ({context_for_logging}): Expected list, but parsed data is type {type(parsed_data)}.")
            return None
            
        if not expect_list and not isinstance(parsed_data, dict):
            if isinstance(parsed_data, list) and len(parsed_data) == 1 and isinstance(parsed_data[0], dict):
                return parsed_data[0]
            logger.warning(f"extract_json_robustly ({context_for_logging}): Expected dict, but parsed data is type {type(parsed_data)}.")
            return None

        return parsed_data
    except json.JSONDecodeError as e:
        logger.error(f"extract_json_robustly ({context_for_logging}): JSONDecodeError: {e}. Attempted to parse: >>>{json_str_to_parse[:500]}<<< (length {len(json_str_to_parse)})")
        return None