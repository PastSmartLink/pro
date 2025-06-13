# adk_sportsomegapro/agents/chief_scout.py
import json
import logging
from typing import Dict, Any, List, cast
from datetime import datetime, timezone

# --- ADK & Project Imports ---
from adk_placeholders import Agent 
from services.gemini_service import GeminiService
from adk_utils import extract_json_robustly
from adk_prompt_manager import prompt_manager 

logger = logging.getLogger(__name__)

class ChiefScoutAgent(Agent):
    """
    Primary agent for dossier analysis, synthesis, and final JSON construction.
    This final version correctly reads from and WRITES to the shared plan state,
    ensuring a seamless handover of intelligence between all stages.
    """
    def __init__(self, model_name: str):
        super().__init__(name="ChiefScoutAgent", description="Orchestrates main analysis and dossier creation.")
        self.gemini_service = GeminiService(model_name=model_name)
        self.t_a_off: str = "Team A"
        self.t_b_off: str = "Team B"

    def _set_teams_from_state(self, state: Dict[str, Any]):
        """Helper to safely set team names from the current state for contextual prompts."""
        baseline_data = state.get("baseline_data") 
        if isinstance(baseline_data, dict):
            self.t_a_off = baseline_data.get("team_a_name_official", state.get("input", {}).get("team_a", "Team A"))
            self.t_b_off = baseline_data.get("team_b_name_official", state.get("input", {}).get("team_b", "Team B"))

    async def execute_step(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically executes the requested stage for this agent."""
        methods_map = {
            "stage_2_initial_analysis": self._stage_2_initial_analysis,
            "stage_3_news_synthesis": self._stage_3_news_synthesis,
            "stage_7_narrative_synthesis": self._stage_7_narrative_synthesis,
            "stage_8_hidden_gems": self._stage_8_hidden_gems,
            "stage_8_5_alternative_perspectives": self._stage_8_5_alternative_perspectives,
            "stage_9_json_dossier": self._stage_9_json_dossier,
        }
        self._set_teams_from_state(state)

        if step_name in methods_map:
            return await methods_map[step_name](state, tools)
        
        return {"error": f"{self.name}: Unknown step '{step_name}'."}

    async def _stage_2_initial_analysis(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 2 - Initial Analysis")
        
        # <<< FINAL POLISH >>>
        # The dossier_plan now ensures baseline_data is present. This stage's job
        # is to *analyze* that data. We construct the prompt with full context.
        prompt_template = prompt_manager.get_prompt('stage_2_initial_analysis')
        baseline_data = state.get("baseline_data", {"error": "Baseline data was missing from plan state."})
        
        prompt_for_llm = f"Baseline Data for {self.t_a_off} vs {self.t_b_off}:\n```json\n{json.dumps(baseline_data, indent=2, default=str)}\n```\n\nTASK: {prompt_template}"
        
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        state["current_overall_analysis"] = response  # WRITE analysis to shared state
        logger.info(f"{self.name}: Stage 2 COMPLETED.")
        return {"status": "completed"}

    async def _stage_3_news_synthesis(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 3 - News Synthesis")
        prompt_template = prompt_manager.get_prompt('stage_3_news_synthesis')
        
        analysis_context = state.get("current_overall_analysis", "Initial analysis missing.")
        news_context = state.get("baseline_data", {}).get("key_news_summary_info", "No news summary available.")
        
        prompt_for_llm = f"Analysis Context:\n{analysis_context}\n\nBaseline News:\n{news_context}\n\nTASK for {self.t_a_off} vs {self.t_b_off}: {prompt_template}"
        
        response = await self.gemini_service.call_model_async(prompt_for_llm)
        state["current_overall_analysis"] = response  # WRITE updated analysis to shared state
        logger.info(f"{self.name}: Stage 3 COMPLETED.")
        return {"status": "completed"}

    async def _stage_7_narrative_synthesis(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 7 - Narrative Synthesis")
        prompt_template = prompt_manager.get_prompt('stage_7_narrative_generation')
        full_analysis_context = state.get("current_overall_analysis", "Complete analysis from previous stages is missing.")
        
        prompt_for_llm = f"Final Integrated Analysis Context:\n{full_analysis_context}\n\nTASK for {self.t_a_off} vs {self.t_b_off}: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        state["final_narrative_json"] = response # WRITE narrative JSON to shared state
        logger.info(f"{self.name}: Stage 7 COMPLETED.")
        return {"status": "completed"}

    async def _stage_8_hidden_gems(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8 - Hidden Gems")
        prompt_template = prompt_manager.get_prompt('stage_8_hidden_gems')
        narrative_json_str = state.get("final_narrative_json", '{"executive_summary_narrative": "Narrative unavailable."}')
        narrative_context = extract_json_robustly(narrative_json_str).get("executive_summary_narrative", "Analysis context is missing.")

        prompt_for_llm = f"Based on the following analysis for {self.t_a_off} vs {self.t_b_off}:\n{narrative_context}\n\nTASK: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        parsed_gems = extract_json_robustly(response, expect_list=True) or []
        state["hidden_gems"] = parsed_gems # WRITE gems to shared state
        logger.info(f"Stage 8 identified {len(parsed_gems)} Hidden Gems.")
        return {"status": "completed"}

    async def _stage_8_5_alternative_perspectives(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8.5 - Alternative Viewpoints")
        prompt_template = prompt_manager.get_prompt('stage_8_5_alternative_perspectives') # Assumes prompt file exists
        narrative_str = state.get("final_narrative_json", '{"executive_summary_narrative": "Narrative unavailable."}')
        narrative_context = extract_json_robustly(narrative_str).get("executive_summary_narrative", "Analysis context is missing.")
        
        prompt_for_llm = f"Your primary narrative is: '{narrative_context[:400]}...'\n\nTASK for {self.t_a_off} vs {self.t_b_off}: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        
        parsed_perspectives = extract_json_robustly(response, expect_list=True) or []
        state["alternative_perspectives"] = parsed_perspectives # WRITE perspectives to shared state
        logger.info(f"Stage 8.5 identified {len(parsed_perspectives)} Alternative Perspectives.")
        return {"status": "completed"}

    async def _stage_9_json_dossier(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 9 - Final Dossier Structuring")
        prompt_template_s9 = prompt_manager.get_prompt('stage_9_dossier_structuring')

        # Gather all prerequisites from the shared state
        context_for_final_prompt = {
            "Match Title": state.get("baseline_data", {}).get("match_title", f"{self.t_a_off} vs {self.t_b_off}"),
            "Baseline Data": state.get("baseline_data", {}),
            "Main Narrative Parts": extract_json_robustly(state.get("final_narrative_json", "{}")),
            "Hidden Gems": state.get("hidden_gems", []),
            "Alternative Perspectives": state.get("alternative_perspectives", [])
        }
        
        prompt_for_llm = f"CONTEXT:\n```json\n{json.dumps(context_for_final_prompt, indent=2, default=str)}\n```\n\nTASK: Populate this exact JSON schema: {prompt_template_s9}"
        response_text = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json", "max_output_tokens": 8192})
        
        final_dossier = extract_json_robustly(response_text)
        if final_dossier and isinstance(final_dossier, dict):
            # Add final metadata before finalizing
            final_dossier["provenance"] = {
                 "production_credit": "A Hans Johannes Schulte Production for SPORTSΩmegaPRO²",
                 "engine_name": "The Manna Maker Engine",
                 "generation_timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            # WRITE THE FINAL PRODUCT TO THE SHARED STATE
            state["dossier_json"] = final_dossier
            logger.info("Stage 9 COMPLETED. Final dossier has been successfully generated.")
            return {"status": "completed"}
        else:
            error_msg = f"Failed to parse the final dossier JSON in Stage 9. AI Response Snippet: {response_text[:300]}"
            state["dossier_json"] = {"error": error_msg}
            return {"error": error_msg}
