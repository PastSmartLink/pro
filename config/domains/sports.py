# adk_sportsomegapro/config/domains/sports.py

SPORTS_CONFIG = {
    "name": "sports",
    "description": "Configuration for generating SPORTSΩmegaPRO Scouting Dossiers for sports matches.",
    
    "lead_analyst_agent": { # This would map to ChiefScoutAgent for now
        "model_name": "gemini-2.5-flash-preview-05-20", # Default, can be overridden by main.py os.getenv
        "persona_prompt_segment": (
            "You are the Chief Scout for SPORTSΩmega PRO, an elite sports intelligence platform. "
            "Your analysis is insightful, narrative-driven, and uncovers hidden details. "
            "You follow instructions meticulously and aim to provide comprehensive, high-quality output. "
            "If asked to output JSON, ensure it is valid and complete according to the schema provided in the user prompt."
        ),
        # Prompt templates could be further broken down by stage if main agents were more generic
    },
    "research_coordinator_agent": { # This would map to ResearchOrchestratorAgent
        "model_name": "gemini-2.5-flash",
        "persona_prompt_segment": (
            "You are a specialized research coordinator for SPORTSΩmega PRO. Your role is to identify deep, "
            "non-obvious strategic angles, define precise research queries for external tools, "
            "and critically synthesize research findings into the ongoing analysis."
        ),
    },

    "tools": {
        # Tool "name" here would be a logical name used by the plan/agent.
        # The "class" would be the Python class name for instantiation in main.py's tool_registry.
        "PrimaryContextDataProviderTool": "BaselineDataTool", 
        "ExternalInformationResearchTool": ["PerplexityResearchTool"] 
    },

    # Could eventually hold the CSMP Stage 9 JSON schema for validation or generation guidance
    "output_schema_description_stage9": "The standard Ωmega Scouting Dossier JSON structure as defined in CSMP v3.1.",
    
    # For dynamic loading of render function if needed (currently main.py imports it directly)
    "render_function_path_for_output": "dossier_generator._render_dossier_json_to_markdown" 
}
