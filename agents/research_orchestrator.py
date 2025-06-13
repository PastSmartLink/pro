# adk_sportsomegapro/agents/research_orchestrator.py
import json
import logging
import asyncio
from typing import Dict, Any, List, cast

# --- ADK & Project Imports ---
from adk_placeholders import Agent
from services.gemini_service import GeminiService
from adk_utils import extract_json_robustly
from adk_prompt_manager import prompt_manager 

logger = logging.getLogger(__name__)

class ResearchOrchestratorAgent(Agent):
    """
    Manages research question generation, parallelized execution, and iterative integration.
    This version is hardened against inconsistent AI output formats.
    """
    def __init__(self, model_name: str):
        super().__init__(name="ResearchOrchestratorAgent", description="Manages deep research workflow.")
        self.gemini_service = GeminiService(model_name=model_name)
        self.t_a_off: str = "Team A"
        self.t_b_off: str = "Team B"

    def _set_teams_from_state(self, state: Dict[str, Any]):
        """Safely sets team names from the current state."""
        baseline_data = state.get("baseline_data") 
        if isinstance(baseline_data, dict):
            self.t_a_off = baseline_data.get("team_a_name_official", "Team A")
            self.t_b_off = baseline_data.get("team_b_name_official", "Team B")
        else:
            self.t_a_off = state.get("input", {}).get("team_a", "Team A")
            self.t_b_off = state.get("input", {}).get("team_b", "Team B")

    async def execute_step(self, step_name: str, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically executes the requested research stage."""
        self._set_teams_from_state(state) 
        
        methods_map = {
            "stage_4_question_generation": self._stage_4_question_generation,
            "stage_5_research_execution": self._stage_5_research_execution_parallel,
            "stage_6_finding_integration": self._stage_6_iterative_integration,
        }
        if step_name in methods_map:
            return await methods_map[step_name](state, tools)
        
        return {"error": f"{self.name}: Unknown step '{step_name}'."}

    async def _stage_4_question_generation(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 4 - SUPERGROK Question Generation")
        prompt_template = prompt_manager.get_prompt('stage_4_supergrok_inquiry')
        current_analysis = state.get("current_overall_analysis", "Analysis context unavailable.")
        
        prompt_for_llm = f"Context for {self.t_a_off} vs {self.t_b_off}:\n{current_analysis}\n\nTask: {prompt_template}"
        response_text = await self.gemini_service.call_model_async(prompt_for_llm, {"response_mime_type": "application/json"})
        
        parsed_questions = extract_json_robustly(response_text, expect_list=True)
        if isinstance(parsed_questions, list) and parsed_questions:
            state["research_questions"] = cast(List[Dict[str,str]], parsed_questions)
            logger.info(f"Stage 4 identified {len(parsed_questions)} SUPERGROK questions.")
            return {"status": "completed"}
        return {"error": f"Failed to parse SUPERGROK questions. Snippet: {response_text[:200]}"}

    async def _execute_single_perplexity_query(self, q_item: Any, perplexity_tool: Any) -> Dict[str, Any]:
        """
        Helper for parallel execution of Perplexity queries.
        <<< HARDENED FIX IS HERE >>>
        This function now handles both dict and str inputs for q_item.
        """
        question = "Unknown Question"
        query = ""

        if isinstance(q_item, dict):
            # This is the expected, ideal case
            question = q_item.get("question", "Question text missing")
            query = q_item.get("perplexity_query_to_run", "")
        elif isinstance(q_item, str):
            # This is the fallback for when the AI returns a list of strings
            logger.warning(f"Stage 5 processing a string item: '{q_item[:70]}...'. Treating string as both question and query.")
            question = q_item
            query = q_item
        else:
            # Handle other unexpected types gracefully
            logger.error(f"Stage 5 received an unexpected item type: {type(q_item)}")
            return {"question": "Invalid Item", "query_used": "", "finding_text": f"Error: Received unexpected item type {type(q_item)}"}

        if query:
            finding = await perplexity_tool.execute({"query_string": query})
            return {"question": question, "query_used": query, "finding_text": finding}
        
        return {"question": question, "query_used": "", "finding_text": "Error: Empty query was provided or generated."}

    async def _stage_5_research_execution_parallel(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 5 - Parallel Research Execution")
        questions = state.get("research_questions", [])
        perplexity_tool = tools.get("PerplexityResearchTool")

        if not questions or not perplexity_tool:
            state["perplexity_findings"] = []
            return {"status": "skipped", "reason": "No questions or tool unavailable"}

        # The rest of this function remains the same as it correctly handles tasks
        tasks = [self._execute_single_perplexity_query(q, perplexity_tool) for q in questions]
        all_findings = await asyncio.gather(*tasks)
        state["perplexity_findings"] = all_findings
        logger.info(f"Stage 5 COMPLETED. Executed {len(all_findings)} research tasks.")
        return {"status": "completed"}

    async def _stage_6_iterative_integration(self, state: Dict[str, Any], tools: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"{self.name}: Executing Stage 6 - Iterative Findings Integration")
        prompt_template = prompt_manager.get_prompt('stage_6_findings_integration')
        findings = state.get("perplexity_findings", [])
        current_analysis = state.get("current_overall_analysis", "")
        
        if not findings:
            return {"status": "skipped", "reason": "No findings to integrate."}
        
        for finding_dict in findings:
            prompt_for_llm = (f"Current Analysis:\n{current_analysis}\n\n"
                              f"New Research Finding:\n```json\n{json.dumps(finding_dict, indent=2)}\n```\n\n"
                              f"Task: {prompt_template}")
            current_analysis = await self.gemini_service.call_model_async(prompt_for_llm)
            logger.debug(f"Integrated finding for question: {finding_dict.get('question', 'N/A')[:50]}...")
        
        state["current_overall_analysis"] = current_analysis 
        logger.info(f"Stage 6 COMPLETED. Integrated {len(findings)} findings.")
        return {"status": "completed"}
