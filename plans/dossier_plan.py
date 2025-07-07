import logging
import json 
from typing import Dict, Any, List

logger = logging.getLogger("DossierGenerationPlan")

class DossierGenerationPlan:
    def __init__(self):
        self.csmp_stages_flow: List[tuple] = [
            ("ChiefScoutAgent", "stage_2_initial_analysis"),
            ("ChiefScoutAgent", "stage_3_news_synthesis"),
            ("ResearchOrchestratorAgent", "stage_4_question_generation"),
            ("ResearchOrchestratorAgent", "stage_5_research_execution"),
            ("ResearchOrchestratorAgent", "stage_6_finding_integration"),
            ("ChiefScoutAgent", "stage_7_narrative_synthesis"),
            ("ChiefScoutAgent", "stage_8_hidden_gems"),
            ("ChiefScoutAgent", "stage_8_5_alternative_perspectives"),
            ("ChiefScoutAgent", "stage_8_6_red_team_analysis"),
            ("ChiefScoutAgent", "stage_9_5_dossier_structuring_make_super_prompt"),
            ("ChiefScoutAgent", "stage_10_refinement_and_scoring"),
            ("ChiefScoutAgent", "stage_10_5_score_prediction"),
            ("ChiefScoutAgent", "stage_11_self_optimization"),
            ("ChiefScoutAgent", "stage_12_first_principles_validation"),
            ("ChiefScoutAgent", "stage_13_cross_domain_mapping"),
            ("ChiefScoutAgent", "stage_14_visualization_hypothesis"),
            ("ChiefScoutAgent", "stage_15_sentiment_calibration"),
            ("ChiefScoutAgent", "stage_16_predictive_scenarios"),
            ("ChiefScoutAgent", "stage_17_ethical_review"),
            ("ChiefScoutAgent", "stage_18_user_engagement_optimization"),
            ("ChiefScoutAgent", "stage_19_metadata_enrichment"),
            ("ChiefScoutAgent", "stage_20_final_validation")
        ]
        logger.info(f"{type(self).__name__} initialized with {len(self.csmp_stages_flow)} stages. AGI LEVEL: 100%")

    async def execute(self, initial_input: Dict[str, Any], agents: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        plan_state: Dict[str, Any] = {
            "input": initial_input,
            "plan_execution_log": [],
            "dossier_json": None
        }
        logger.info(f"PLAN EXECUTION STARTED for {initial_input.get('match_id')}")

        baseline_tool = tools.get("BaselineDataTool")
        if baseline_tool:
            plan_state['baseline_data'] = await baseline_tool.execute(initial_input)
            if plan_state['baseline_data'].get("error"):
                 logger.error(f"Halting plan due to fatal error in BaselineDataTool: {plan_state['baseline_data']['error']}")
                 plan_state['dossier_json'] = {"error": f"Failed to get baseline data: {plan_state['baseline_data']['error']}"}
                 return plan_state
        else:
             plan_state['dossier_json'] = {"error": "BaselineDataTool not found."}
             return plan_state

        for agent_key, step_name in self.csmp_stages_flow:
            step_desc = f"CSMP {step_name}"
            logger.info(f"PLAN: ==> Attempting: {step_desc} (Agent: {agent_key})")
            plan_state["plan_execution_log"].append({"severity": "INFO", "message": f"Attempting {step_desc}"})

            agent_instance = agents.get(agent_key)
            if not agent_instance:
                error_msg = f"Agent '{agent_key}' not found."
                logger.critical(f"PLAN HALTED: {error_msg}")
                plan_state["dossier_json"] = {"error": error_msg}
                return plan_state
            
            try:
                step_result = await agent_instance.execute_step(step_name=step_name, state=plan_state, tools=tools)
                if step_result and step_result.get("error"):
                    error_message = step_result.get("error", "Unknown error")
                    logger.error(f"PLAN: Stage '{step_desc}' FAILED with error: {error_message}")
                    plan_state["plan_execution_log"].append({"severity": "ERROR", "step": step_desc, "message": error_message})
                    plan_state["dossier_json"] = {"error": f"Plan failed at {step_desc}: {error_message}"}
                    return plan_state
                else:
                    logger.info(f"PLAN: Successfully COMPLETED --> {step_desc}")

            except Exception as e:
                exception_err = f"PLAN CRITICAL EXCEPTION during '{step_desc}': {e}"
                logger.critical(exception_err, exc_info=True)
                plan_state["dossier_json"] = {"error": exception_err}
                return plan_state

        logger.info("PLAN: All CSMP stages processed successfully.")
        return plan_state
