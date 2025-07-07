# adk_sportsomegapro/agents/chief_scout.py - FINAL, RELIABLE VERSION
import json
import logging
from typing import Dict, Any, List, cast
from datetime import datetime, timezone

from adk_placeholders import Agent 
from services.gemini_service import GeminiService
from adk_utils import extract_json_robustly
from adk_prompt_manager import prompt_manager 

logger = logging.getLogger(__name__)

class ChiefScoutAgent(Agent):
    def __init__(self, model_name: str):
        super().__init__(name="ChiefScoutAgent", description="Orchestrates main analysis and dossier creation.")
        self.gemini_service = GeminiService(model_name=model_name)
        self.t_a_off: str = "Team A"
        self.t_b_off: str = "Team B"

    def _set_teams_from_state(self, state: Dict[str, Any]):
        baseline_data = state.get("baseline_data") 
        if isinstance(baseline_data, dict):
            self.t_a_off = baseline_data.get("team_a_name_official", "Team A")
            self.t_b_off = baseline_data.get("team_b_name_official", "Team B")

    async def execute_step(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        self._set_teams_from_state(state)
        
        methods_map = {
            "stage_2_initial_analysis": self._stage_2_initial_analysis,
            "stage_3_news_synthesis": self._stage_3_news_synthesis,
            "stage_7_narrative_generation": self._stage_7_narrative_synthesis,
            "stage_8_hidden_gems": self._stage_8_hidden_gems,
            "stage_8_5_alternative_perspectives": self._stage_8_5_alternative_perspectives,
            "stage_8_6_red_team_counter_narrative": self._stage_8_6_red_team_analysis,
            "stage_9_dossier_structuring": self._stage_9_json_dossier, # Re-enabled the working method
            "stage_10_5_score_prediction": self._unimplemented_agi_stage,
            "stage_11_prompt_self_optimization": self._unimplemented_agi_stage,
            "stage_12_first_principles_validation": self._unimplemented_agi_stage,
            "stage_13_cross_domain_mapping": self._unimplemented_agi_stage,
            "stage_14_visualization_hypothesis": self._unimplemented_agi_stage,
            "stage_15_sentiment_calibration": self._unimplemented_agi_stage,
            "stage_16_predictive_scenarios": self._unimplemented_agi_stage,
            "stage_17_ethical_review": self._unimplemented_agi_stage,
            "stage_18_user_engagement_optimization": self._unimplemented_agi_stage,
            "stage_19_metadata_enrichment": self._unimplemented_agi_stage,
            "stage_20_final_validation": self._unimplemented_agi_stage
        }
        
        if step_name in methods_map:
            return await methods_map[step_name](step_name, state, tools)
        
        return {"error": f"{self.name}: Unknown step '{step_name}'."}

    async def _unimplemented_agi_stage(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.warning(f"'{step_name}' is not fully implemented. Passing state through.")
        state[step_name] = {"status": "skipped_not_implemented"}
        return {"status": "completed"}
    
    # --- RESTORED ALL YOUR ORIGINAL, WORKING STAGE METHODS BELOW ---
    async def _stage_2_initial_analysis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 2 - Initial Analysis")
        prompt_template = prompt_manager.get_prompt(step_name)
        baseline_data = state.get("baseline_data", {})
        prompt_for_llm = f"Baseline Data:\n```json\n{json.dumps(baseline_data, indent=2, default=str)}\n```\n\nTASK: {prompt_template}"
        state["current_overall_analysis"] = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        logger.info(f"{self.name}: Stage 2 COMPLETED.")
        return {"status": "completed"}

    async def _stage_3_news_synthesis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 3 - News Synthesis")
        prompt_template = prompt_manager.get_prompt(step_name)
        analysis_context = state.get("current_overall_analysis", "Initial analysis missing.")
        news_context = state.get("baseline_data", {}).get("key_news_summary_info", "No news summary available.")
        prompt_for_llm = f"Analysis Context:\n{analysis_context}\n\nBaseline News:\n{news_context}\n\nTASK: {prompt_template}"
        state["current_overall_analysis"] = await self.gemini_service.call_model_async(prompt_for_llm)
        logger.info(f"{self.name}: Stage 3 COMPLETED.")
        return {"status": "completed"}

    async def _stage_7_narrative_synthesis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 7 - Narrative Synthesis")
        prompt_template = prompt_manager.get_prompt(step_name)
        context = state.get("current_overall_analysis", "Analysis missing.")
        prompt_for_llm = f"Context:\n{context}\n\nTASK: {prompt_template}"
        state["final_narrative_json"] = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        logger.info(f"{self.name}: Stage 7 COMPLETED.")
        return {"status": "completed"}

    async def _stage_8_hidden_gems(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8 - Hidden Gems")
        prompt_template = prompt_manager.get_prompt(step_name)
        narrative_context = extract_json_robustly(state.get("final_narrative_json", "{}")).get("executive_summary_narrative", "Context missing.")
        prompt_for_llm = f"Context:\n{narrative_context}\n\nTASK: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        state["hidden_gems"] = extract_json_robustly(response, expect_list=True) or []
        logger.info(f"Stage 8 identified {len(state['hidden_gems'])} gems.")
        return {"status": "completed"}

    async def _stage_8_5_alternative_perspectives(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8.5 - Alternative Viewpoints")
        prompt_template = prompt_manager.get_prompt(step_name)
        narrative_context = extract_json_robustly(state.get("final_narrative_json", "{}")).get("executive_summary_narrative", "Context missing.")
        prompt_for_llm = f"Primary Narrative:\n'{narrative_context}'\n\nTASK: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        state["alternative_perspectives"] = extract_json_robustly(response, expect_list=True) or []
        logger.info(f"Stage 8.5 identified {len(state['alternative_perspectives'])} perspectives.")
        return {"status": "completed"}

    async def _stage_8_6_red_team_analysis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8.6 - Red Team Analysis")
        prompt_template = prompt_manager.get_prompt(step_name)
        narrative_context = extract_json_robustly(state.get("final_narrative_json", "{}")).get("executive_summary_narrative", "Context missing.")
        prompt_for_llm = f"Primary Analysis to be Challenged:\n{narrative_context}\n\nTASK: {prompt_template}"
        state["red_team_critique_json"] = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        logger.info(f"{self.name}: Stage 8.6 COMPLETED.")
        return {"status": "completed"}
    
    async def _stage_9_json_dossier(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 9 - Final Dossier Structuring (PROVEN METHOD)")
        prompt_template = prompt_manager.get_prompt(step_name)
        context = {
            "Match Info": state.get("input"),
            "Baseline Data": state.get("baseline_data", {}),
            "Narrative JSON": extract_json_robustly(state.get("final_narrative_json", "{}")),
            "Hidden Gems": state.get("hidden_gems", []),
            "Alternative Perspectives": state.get("alternative_perspectives", []),
            "Red Team Critique": extract_json_robustly(state.get("red_team_critique_json", "{}"))
        }
        prompt_for_llm = f"CONTEXT:\n```json\n{json.dumps(context, indent=2, default=str)}\n```\n\nTASK: {prompt_template}"
        response_text = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json", "max_output_tokens": 8192})
        
        dossier = extract_json_robustly(response_text)
        if dossier and isinstance(dossier, dict):
            state["dossier_json"] = dossier
            logger.info("Stage 9 COMPLETED. Final dossier has been successfully generated.")
            return {"status": "completed"}
        else:
            return {"error": f"Failed to parse final dossier in Stage 9. Snippet: {response_text[:200]}"}
