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
        super().__init__(name="ChiefScoutAgent", description="Core reasoning and AGI synthesis engine.")
        self.gemini_service = GeminiService(model_name=model_name)
        self.t_a_off: str = "Team A"
        self.t_b_off: str = "Team B"

    def _set_teams_from_state(self, state: Dict[str, Any]):
        baseline_data = state.get("baseline_data") 
        if isinstance(baseline_data, dict):
            self.t_a_off = baseline_data.get("team_a_name_official", state.get("input", {}).get("team_a", "Team A"))
            self.t_b_off = baseline_data.get("team_b_name_official", state.get("input", {}).get("team_b", "Team B"))

    async def execute_step(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        self._set_teams_from_state(state)

        methods_map = {
            "stage_2_initial_analysis": self._stage_2_initial_analysis,
            "stage_3_news_synthesis": self._stage_3_news_synthesis,
            "stage_7_narrative_synthesis": self._stage_7_narrative_synthesis,
            "stage_8_hidden_gems": self._stage_8_hidden_gems,
            "stage_8_5_alternative_perspectives": self._stage_8_5_alternative_perspectives,
            "stage_8_6_red_team_analysis": self._stage_8_6_red_team_analysis,
            "stage_9_5_dossier_structuring_make_super_prompt": self._stage_9_5_make_super_prompt,
            "stage_10_refinement_and_scoring": self._stage_10_dossier_generation,
            "stage_10_5_score_prediction": self._unimplemented_agi_stage,
            "stage_11_self_optimization": self._unimplemented_agi_stage,
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
        
        logger.error(f"{self.name}: Unknown step '{step_name}'. This agent is not equipped to handle this stage.")
        return {"error": f"{self.name}: Unknown step '{step_name}'."}

    async def _stage_2_initial_analysis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 2 - Initial Analysis")
        prompt_template = prompt_manager.get_prompt(step_name)
        baseline_data = state.get("baseline_data", {"error": "Baseline data was missing from plan state."})
        prompt_for_llm = f"Baseline Data for {self.t_a_off} vs {self.t_b_off}:\n```json\n{json.dumps(baseline_data, indent=2, default=str)}\n```\n\nTASK: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        state["current_overall_analysis"] = response
        logger.info(f"{self.name}: Stage 2 COMPLETED.")
        return {"status": "completed"}

    async def _stage_3_news_synthesis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 3 - News Synthesis")
        prompt_template = prompt_manager.get_prompt(step_name)
        analysis_context = state.get("current_overall_analysis", "Initial analysis missing.")
        news_context = state.get("baseline_data", {}).get("key_news_summary_info", "No news summary available.")
        prompt_for_llm = f"Analysis Context:\n{analysis_context}\n\nBaseline News:\n{news_context}\n\nTASK for {self.t_a_off} vs {self.t_b_off}: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm)
        state["current_overall_analysis"] = response
        logger.info(f"{self.name}: Stage 3 COMPLETED.")
        return {"status": "completed"}

    async def _stage_7_narrative_synthesis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 7 - Narrative Synthesis")
        prompt_template = prompt_manager.get_prompt('stage_7_narrative_generation')
        full_analysis_context = state.get("current_overall_analysis", "Complete analysis from previous stages is missing.")
        prompt_for_llm = f"Final Integrated Analysis Context:\n{full_analysis_context}\n\nTASK for {self.t_a_off} vs {self.t_b_off}: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        state["final_narrative_json"] = response
        logger.info(f"{self.name}: Stage 7 COMPLETED.")
        return {"status": "completed"}

    async def _stage_8_hidden_gems(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8 - Hidden Gems")
        prompt_template = prompt_manager.get_prompt(step_name)
        narrative_json_str = state.get("final_narrative_json", '{"executive_summary_narrative": "Narrative unavailable."}')
        narrative_context = extract_json_robustly(narrative_json_str).get("executive_summary_narrative", "Analysis context is missing.")
        prompt_for_llm = f"Based on the following analysis for {self.t_a_off} vs {self.t_b_off}:\n{narrative_context}\n\nTASK: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        parsed_gems = extract_json_robustly(response, expect_list=True) or []
        state["hidden_gems"] = parsed_gems
        logger.info(f"Stage 8 identified {len(parsed_gems)} Hidden Gems.")
        return {"status": "completed"}

    async def _stage_8_5_alternative_perspectives(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8.5 - Alternative Viewpoints")
        prompt_template = prompt_manager.get_prompt(step_name)
        narrative_str = state.get("final_narrative_json", '{"executive_summary_narrative": "Narrative unavailable."}')
        narrative_context = extract_json_robustly(narrative_str).get("executive_summary_narrative", "Analysis context is missing.")
        prompt_for_llm = f"Your primary narrative is: '{narrative_context[:400]}...'\n\nTASK for {self.t_a_off} vs {self.t_b_off}: {prompt_template}"
        response = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        parsed_perspectives = extract_json_robustly(response, expect_list=True) or []
        state["alternative_perspectives"] = parsed_perspectives
        logger.info(f"Stage 8.5 identified {len(parsed_perspectives)} Alternative Perspectives.")
        return {"status": "completed"}

    async def _stage_8_6_red_team_analysis(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 8.6 - Red Team Analysis")
        prompt_template = prompt_manager.get_prompt(step_name)
        current_analysis = state.get("current_overall_analysis", "No primary analysis available to critique.")
        prompt_for_llm = (f"Primary Analysis to Critique:\n{current_analysis}\n\n"
                          f"Red Team Task: {prompt_template}")
        red_team_critique = await self.gemini_service.call_model_async(prompt_for_llm)
        state["red_team_critique"] = red_team_critique
        logger.info(f"{self.name}: Stage 8.6 COMPLETED. Generated adversarial critique.")
        return {"status": "completed"}

    async def _stage_9_5_make_super_prompt(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 9.5 - Meta-Prompt Synthesis")
        prompt_template = prompt_manager.get_prompt('stage_9_5_dossier_structuring_make_super_prompt')
        context_for_synthesis = {
            "initial_analysis": extract_json_robustly(state.get("current_overall_analysis", "{}")),
            "narrative": extract_json_robustly(state.get("final_narrative_json", "{}")),
            "hidden_gems": state.get("hidden_gems", []),
            "alternative_perspectives": state.get("alternative_perspectives", []),
            "red_team_critique": state.get("red_team_critique", "Not provided."),
        }
        input_context_str = json.dumps(context_for_synthesis, indent=2, default=str)
        prompt_for_llm = (f"Analytical Dossier (Stages 2-8.6):\n```json\n{input_context_str}\n```\n\n"
                          f"Synthesis Task: {prompt_template}")
        super_prompt = await self.gemini_service.call_model_async(prompt_for_llm)
        state["super_prompt"] = super_prompt
        logger.info(f"{self.name}: Stage 9.5 COMPLETED. Generated Super Prompt for final dossier generation.")
        return {"status": "completed"}

    async def _stage_10_dossier_generation(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 10 - Final Dossier Generation from Super Prompt")
        super_prompt = state.get("super_prompt")
        if not super_prompt:
            return {"error": "Super Prompt from Stage 9.5 is missing. Cannot generate final dossier."}

        response_text = await self.gemini_service.call_model_async(super_prompt, {"response_mime_type": "application/json", "max_output_tokens": 8192})
        final_dossier = extract_json_robustly(response_text)
        
        if final_dossier and isinstance(final_dossier, dict):
            final_dossier["provenance"] = {
                 "production_credit": "A Hans Johannes Schulte Production for AIOS.ICU",
                 "engine_name": "Manna Maker Cognitive Factory",
                 "cognitive_stages_executed": 22,
                 "generation_timestamp_utc": datetime.now(timezone.utc).isoformat()
            }
            state["dossier_json"] = final_dossier
            logger.info("Stage 10 COMPLETED. Final AGI dossier has been successfully generated.")
            return {"status": "completed"}
        else:
            error_msg = f"Failed to parse the final dossier JSON in Stage 10. AI Response Snippet: {response_text[:300]}"
            state["dossier_json"] = {"error": error_msg}
            return {"error": error_msg}

    async def _unimplemented_agi_stage(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.warning(f"'{step_name}' is not fully implemented. Passing state through.")
        state[step_name] = {"status": "skipped_not_implemented"}
        return {"status": "completed"}
