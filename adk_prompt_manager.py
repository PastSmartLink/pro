# adk_prompt_manager.py - FINAL UNIFIED AGI IMPLEMENTATION

import os
import json
import logging
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Load environment variables from .env file at the module level
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class StageConfiguration:
    """Configuration for individual CSMP stages"""
    model: str
    prompt_adjustment: str
    data_sources: List[str]
    analysis_depth: str = "standard"

class CognitivePromptManager:
    """Enhanced singleton class for AGI-level cognitive prompt management with dynamic optimization."""
    
    _instance = None
    _is_initialized = False

    def __new__(cls, prefix: str = "CSMP") -> 'CognitivePromptManager':
        if cls._instance is None:
            cls._instance = super(CognitivePromptManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, prefix: str = "CSMP"):
        if self._is_initialized:
            return
        
        self.prefix = prefix
        self.prompts: Dict[str, str] = {}
        self.cognitive_configurations: Dict[str, StageConfiguration] = {}
        self._is_initialized = True
        
        self.model_matrix = {
            "sports": {"standard": "sonar-pro", "deep": "gemini-2.5", "ultra": "gemini-2.5"},
            "finance": {"standard": "gemini-2.5-flash", "deep": "gemini-2.5", "ultra": "gemini-2.5"},
            "geopolitics": {"standard": "sonar-pro", "deep": "gemini-2.5", "ultra": "gemini-2.5"},
            "general": {"standard": "gemini-2.5-flash", "deep": "gemini-2.5", "ultra": "gemini-2.5"}
        }
        
        logger.info(f"CognitivePromptManager initialized for Full 20-Stage AGI operations. Prefix: '{self.prefix}'")

    def cognitive_planning_optimizer(self, env_vars: Dict[str, Any], user_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core AGI function: Generates a full 20-stage cognitive plan."""
        merged_config = {**env_vars, **user_inputs}
        domain_key = merged_config.get("domain_key", "general")
        analysis_depth = merged_config.get("analysis_depth", "standard")
        base_model = self._select_optimal_model(domain_key, analysis_depth)
        
        stage_configs = self._generate_stage_configurations(domain_key, analysis_depth, base_model)
        
        return {
            **stage_configs,
            "report_detail_level": self._determine_report_detail_level(analysis_depth),
            "cognitive_metadata": {
                "active_stages": list(stage_configs.keys()),
                "agi_utilization": "100%",
                "domain_optimization": domain_key,
                "depth_calibration": analysis_depth,
            }
        }

    def _select_optimal_model(self, domain: str, depth: str) -> str:
        """AGI Model Selection Logic"""
        return self.model_matrix.get(domain, self.model_matrix["general"]).get(depth, "gemini-2.5-flash")

    def _generate_stage_configurations(self, domain: str, depth: str, base_model: str) -> Dict[str, Dict[str, Any]]:
        """
        *** UNIFIED CONFIGURATION FOR ALL 20 STAGES ***
        Generate optimized configurations for every known CSMP stage.
        """
        
        # Comprehensive model map for the entire cognitive architecture
        stage_models = {
            "stage_2": base_model,                     # Initial Analysis
            "stage_3": "sonar-pro",                    # News Synthesis (Fast, Real-time)
            "stage_4": "gemini-2.5",                   # SUPERGROK Inquiry (Deep questions)
            "stage_5": "gemini-2.5-flash",             # Perplexity Research (Orchestration call)
            "stage_6": base_model,                     # Findings Integration
            "stage_7": base_model,                     # Narrative Generation
            "stage_8": "gemini-2.5-flash",             # Hidden Gems (Pattern Recognition)
            "stage_8_5": base_model,                   # Alternative Perspectives
            "stage_8_6": "gemini-2.5",                 # Red Team (High-level reasoning)
            "stage_9": "gemini-2.5-flash",             # Dossier Structuring (Formatting)
            "stage_9_5": base_model,                   # Make Super Prompt (Synthesis)
            "stage_10": "gemini-2.5",                  # Refinement (Precision)
            "stage_10_5": "gemini-2.5",                # Score Prediction (Analytical)
            "stage_11": "gemini-2.5",                  # Self-Optimization (Metacognition)
            "stage_12": "gemini-2.5",                  # First Principles (Deep Logic)
            "stage_13": "gemini-2.5",                  # Cross-Domain Mapping (Abstract)
            "stage_14": "gemini-2.5-flash",             # Visualization Hypothesis (Fast)
            "stage_15": "gemini-2.5",                  # Sentiment Calibration (Nuance)
            "stage_16": "gemini-2.5",                  # Predictive Scenarios (Strategic)
            "stage_17": "gemini-2.5",                  # Ethical Review (Critical reasoning)
            "stage_18": "gemini-2.5-flash",             # User Engagement (Personalization)
            "stage_19": "gemini-2.5",                  # Metadata Enrichment (Knowledge Graph)
            "stage_20": "gemini-2.5",                  # Final Validation (QA)
        }
        
        base_sources = ["Perplexity AI", "TRAINING_DATA_URL"]
        
        configurations = {}
        for stage_key, model in stage_models.items():
            # Construct full data source list based on domain
            current_sources = list(base_sources) # Start with a copy
            if domain == "sports":
                current_sources.extend(["ODDS_API", "BaselineDataTool"])
            elif domain == "finance":
                current_sources.extend(["MARKET_DATA_API", "FINANCIAL_NEWS_API"])
            elif domain == "geopolitics":
                current_sources.extend(["GEOPOLITICAL_INTEL", "SENTIMENT_ANALYSIS_API"])

            configurations[stage_key] = {
                "model": model,
                "prompt_adjustment": self._generate_prompt_adjustment(stage_key, domain, depth),
                "data_sources": current_sources[:4] # Limit sources for efficiency
            }
        
        return configurations

    def _generate_prompt_adjustment(self, stage: str, domain: str, depth: str) -> str:
        """Generate dynamic prompt adjustments based on stage, domain, and depth"""
        depth_modifiers = {
            "standard": "Provide concise, actionable insights",
            "deep": "Conduct thorough analysis with detailed reasoning",
            "ultra": "Execute comprehensive examination with multi-layered perspectives"
        }
        domain_contexts = {
            "sports": "Focus on tactical dynamics, player psychology, and statistical anomalies",
            "finance": "Emphasize market volatility, risk assessment, and economic indicators", 
            "geopolitics": "Analyze power dynamics, strategic implications, and systemic risks",
            "general": "Apply universal analytical frameworks with adaptive reasoning"
        }
        
        base_adjustment = depth_modifiers.get(depth, "Provide balanced analysis")
        domain_context = domain_contexts.get(domain, "Apply general analytical principles")
        
        return f"Objective: {stage}. {base_adjustment}. {domain_context}."

    def _determine_report_detail_level(self, analysis_depth: str) -> str:
        """Determine report detail level based on analysis depth"""
        detail_mapping = {
            "standard": "executive_summary",
            "deep": "comprehensive_analysis", 
            "ultra": "exhaustive_intelligence_dossier"
        }
        return detail_mapping.get(analysis_depth, "comprehensive_analysis")

    def has_prompt(self, stage_name: str) -> bool:
        """Checks if a prompt environment variable exists and is not empty."""
        env_var_name = f"{self.prefix}_{stage_name.upper()}_PROMPT"
        prompt_content = os.getenv(env_var_name)
        return bool(prompt_content and prompt_content.strip())

    def get_prompt(self, stage_name: str) -> str:
        """Enhanced prompt retrieval with cognitive optimization"""
        env_var_name = f"{self.prefix}_{stage_name.upper()}_PROMPT"
        
        if env_var_name in self.prompts:
            return self.prompts[env_var_name]

        prompt_content = os.getenv(env_var_name)
        if not prompt_content or not prompt_content.strip():
            error_msg = f"AGI COGNITIVE PROMPT MISSING: '{env_var_name}' required for full AGI operation."
            logger.critical(error_msg)
            raise ValueError(error_msg)

        self.prompts[env_var_name] = prompt_content
        return prompt_content

    def execute_cognitive_planning(self, env_vars: Optional[Dict] = None, user_inputs: Optional[Dict] = None) -> Dict[str, Any]:
        """Main AGI execution function to create the full cognitive plan"""
        return self.cognitive_planning_optimizer(env_vars or {}, user_inputs or {})

prompt_manager = CognitivePromptManager(prefix="CSMP")

def activate_full_agi(domain: str = "general", depth: str = "deep") -> Dict[str, Any]:
    """Activates full 20-stage AGI capabilities"""
    env_vars = {"CSMP_ANALYSIS_DEPTH": depth}
    user_inputs = {"domain_key": domain, "analysis_depth": depth}
    return prompt_manager.execute_cognitive_planning(env_vars, user_inputs)
