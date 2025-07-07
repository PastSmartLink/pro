# adk_sportsomegapro/plans/dossier_plan.py - FINAL, RELIABLE VERSION
import logging
import json 
from typing import Dict, Any, List

logger = logging.getLogger("DossierGenerationPlan")

class DossierGenerationPlan:
    def __init__(self):
        # FIX: Restored the proven 9-stage logic as the core, with AGI stages as additions.
        self.csmp_stages_flow: List[tuple] = [
            ("ChiefScoutAgent", "stage_2_initial_analysis"),
            ("ChiefScoutAgent", "stage_3_news_synthesis"),
            ("ResearchOrchestratorAgent", "stage_4_supergrok_inquiry"),
            ("ResearchOrchestratorAgent", "stage_5_perplexity_research"),
            ("ResearchOrchestratorAgent", "stage_6_findings_integration"),
            ("ChiefScoutAgent", "stage_7_narrative_generation"), # Corrected from your file
            ("ChiefScoutAgent", "stage_8_hidden_gems"),
            ("ChiefScoutAgent", "stage_8_5_alternative_perspectives"),
            ("ChiefScoutAgent", "stage_8_6_red_team_counter_narrative"), 
            
            # Use the original, reliable dossier generation as the final content step
            ("ChiefScoutAgent", "stage_9_dossier_structuring"),
            
            # Add advanced AGI stages for future implementation
            ("ChiefScoutAgent", "stage_10_5_score_prediction"),
            ("ChiefScoutAgent", "stage_11_prompt_self_optimization"), 
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
        logger.info(f"{type(self).__name__} initialized with {len(self.csmp_stages_flow)} stages. Using proven generation logic.")

    async def execute(self, initial_input: Dict[str, Any], agents: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        plan_state: Dict[str, Any] = { "input": initial_input, "plan_execution_log": [], "dossier_json": None }
        logger.info(f"PLAN EXECUTION STARTED for {initial_input.get('match_id')}")

        baseline_tool = tools.get("BaselineDataTool")
        if baseline_tool:
            plan_state['baseline_data'] = await baseline_tool.execute(initial_input)
            if plan_state['baseline_data'].get("error"):
                 plan_state['dossier_json'] = {"error": f"Failed on baseline data: {plan_state['baseline_data']['error']}"}
                 return plan_state
        else:
             plan_state['dossier_json'] = {"error": "BaselineDataTool not found."}
             return plan_state

        for agent_key, step_name in self.csmp_stages_flow:
            step_desc = f"CSMP {step_name}"
            logger.info(f"PLAN: ==> Attempting: {step_desc} (Agent: {agent_key})")
            plan_state["plan_execution_log"].append({"message": f"Attempting {step_desc}"})

            agent_instance = agents.get(agent_key)
            if not agent_instance:
                plan_state["dossier_json"] = {"error": f"Agent '{agent_key}' not found."}
                return plan_state
            
            try:
                step_result = await agent_instance.execute_step(step_name=step_name, state=plan_state, tools=tools)
                if step_result and step_result.get("error"):
                    error_message = step_result.get("error", "Unknown error")
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
