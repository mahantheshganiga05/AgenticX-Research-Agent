"""Core Research Agent Implementation.

Coordinates tool selection, step counting, source registry, evidence synthesis,
citation validation, and graceful failure recovery.
"""

import json
import logging
import re
from typing import Optional
from openai import OpenAI, OpenAIError

from app.config import config
from app.agent.state import AgentState
from app.agent.prompts import (
    DECISION_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    CORRECTION_SYSTEM_PROMPT,
)
from app.tools.web_search import web_search
from app.tools.fetch_page import fetch_page
from app.services.citation_validator import CitationValidator

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Autonomous tool-using agent with hard step limits and claim traceability."""

    def __init__(
        self,
        openai_client: Optional[OpenAI] = None,
        max_steps: Optional[int] = None,
    ):
        self.max_steps = max_steps or config.MAX_AGENT_STEPS
        self.model = config.OPENAI_MODEL

        # Initialize OpenAI client if key is configured
        if openai_client:
            self.client = openai_client
        elif config.OPENAI_API_KEY and config.OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            self.client = None

    def run(self, question: str, max_steps: Optional[int] = None) -> AgentState:
        """Execute the full research workflow for a given question.
        
        Args:
            question: The user's research query.
            max_steps: Optional step limit override (capped at self.max_steps).
            
        Returns:
            AgentState containing audit trail, sources, and validated answer.
        """
        effective_max = min(max_steps or self.max_steps, self.max_steps)
        state = AgentState(
            question=question.strip(),
            max_steps=effective_max,
            steps_used=0,
            status="running",
        )

        logger.info(f"Starting research request: '{question}' (Limit: {effective_max} steps)")

        # Verify LLM availability
        if not self.client:
            error_msg = "OpenAI API key is missing or not configured. Set OPENAI_API_KEY in .env."
            logger.warning(error_msg)
            state.add_error(error_msg)
            state.final_answer = (
                "⚠️ **Configuration Error**: OpenAI API key is missing. "
                "Please configure `OPENAI_API_KEY` in the `.env` file to enable the agent reasoning engine."
            )
            state.status = "failed"
            return state

        # =====================================================================
        # AGENT LOOP (Bounded by HARD MAX_AGENT_STEPS limit)
        # =====================================================================
        while state.steps_used < state.max_steps:
            state.steps_used += 1
            current_step = state.steps_used
            logger.info(f"[Step {current_step}/{state.max_steps}] Determining next action...")

            # 1. Ask LLM to decide next action
            decision = self._decide_next_action(state)

            action = decision.get("action", "").lower()
            thought = decision.get("thought", "")
            logger.info(f"[Step {current_step}] Thought: {thought} | Action: {action}")

            # 2. Check stopping action
            if action == "finish":
                reason = decision.get("reason", "Sufficient evidence collected.")
                state.add_tool_record(
                    tool="finish",
                    inputs={"reason": reason},
                    success=True,
                    summary=f"Finished research: {reason}",
                )
                logger.info(f"Agent chose to finish at step {current_step}: {reason}")
                break

            # 3. Execute Tool 1: web_search
            elif action == "web_search":
                query = decision.get("query", state.question).strip()
                result = web_search(query)

                if result.success and result.data:
                    added_ids = []
                    for item in result.data:
                        src = state.register_source(
                            url=item["url"],
                            title=item["title"],
                            snippet=item["snippet"],
                            tool="web_search",
                            retrieval_status="success",
                        )
                        added_ids.append(src.source_id)

                    summary = f"Found {len(result.data)} results for '{query}' ({', '.join(added_ids)})"
                    state.add_tool_record(
                        tool="web_search",
                        inputs={"query": query},
                        success=True,
                        summary=summary,
                    )
                else:
                    err = result.error or result.message or "No results returned."
                    state.add_error(f"web_search failed: {err}")
                    state.add_tool_record(
                        tool="web_search",
                        inputs={"query": query},
                        success=False,
                        summary=f"Search failed/empty: {err}",
                    )

            # 4. Execute Tool 2: fetch_page
            elif action == "fetch_page":
                url = decision.get("url", "").strip()
                result = fetch_page(url)

                if result.success and result.data:
                    data = result.data
                    src = state.register_source(
                        url=data["url"],
                        title=data["title"],
                        snippet=data["content"],
                        tool="fetch_page",
                        retrieval_status="success",
                    )
                    summary = f"Fetched {data['char_count']} chars from [{src.source_id}] {data['title']}"
                    state.add_tool_record(
                        tool="fetch_page",
                        inputs={"url": url},
                        success=True,
                        summary=summary,
                    )
                else:
                    err = result.error or result.message or "Failed to fetch page."
                    state.add_error(f"fetch_page failed for '{url}': {err}")
                    state.add_tool_record(
                        tool="fetch_page",
                        inputs={"url": url},
                        success=False,
                        summary=f"Fetch failed: {err}",
                    )

            # 5. Unknown / fallback action
            else:
                logger.warning(f"Unknown action '{action}' at step {current_step}")
                state.add_tool_record(
                    tool="unknown",
                    inputs=decision,
                    success=False,
                    summary=f"Unrecognized action '{action}'",
                )

            # Check if hard step limit reached
            if state.steps_used >= state.max_steps:
                logger.info(f"Hard step limit ({state.max_steps}) reached. Proceeding to answer synthesis.")
                state.status = "step_limit_reached"

        if state.status != "step_limit_reached":
            state.status = "completed"

        # =====================================================================
        # EVIDENCE SYNTHESIS & CITATION VALIDATION
        # =====================================================================
        self._synthesize_and_validate(state)
        return state

    def _decide_next_action(self, state: AgentState) -> dict:
        """Call LLM with current state to plan next action."""
        # Compile summary of state for prompt
        remaining_steps = state.max_steps - state.steps_used + 1

        sources_summary = []
        for s in state.get_source_list():
            sources_summary.append(
                f"- [{s.source_id}] {s.title} ({s.url}) [status: {s.retrieval_status}, tool: {s.tool}]"
            )
        sources_text = "\n".join(sources_summary) if sources_summary else "No sources collected yet."

        history_summary = []
        for h in state.tool_history:
            status_str = "SUCCESS" if h.success else "FAILED"
            history_summary.append(f"Step {h.step}: {h.tool} ({status_str}) -> {h.summary}")
        history_text = "\n".join(history_summary) if history_summary else "No tools executed yet."

        user_prompt = f"""RESEARCH QUESTION: "{state.question}"

CURRENT EXECUTION STATUS:
- Current Step: {state.steps_used}
- Steps Remaining: {remaining_steps}
- Hard Step Limit: {state.max_steps}

TOOL HISTORY:
{history_text}

REGISTERED SOURCES:
{sources_text}

RECENT ERRORS (if any):
{chr(10).join(state.errors[-3:]) if state.errors else "None"}

Decide your next action (web_search, fetch_page, or finish) based on the evidence collected so far.
Output ONLY a valid JSON object.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content.strip()
            return json.loads(raw_content)
        except Exception as e:
            logger.error(f"LLM decision call failed: {e}")
            state.add_error(f"LLM decision error: {str(e)}")
            # Safe heuristic fallback if LLM decision call fails:
            # If no sources, try web_search with question; else finish
            if not state.sources:
                return {
                    "thought": "LLM call encountered an issue. Initiating primary web search as fallback.",
                    "action": "web_search",
                    "query": state.question,
                }
            return {
                "thought": "LLM call encountered an issue. Finishing with existing evidence.",
                "action": "finish",
                "reason": "Fallback due to planning error.",
            }

    def _synthesize_and_validate(self, state: AgentState) -> None:
        """Synthesize final answer from collected sources and validate citations."""
        successful_sources = {
            sid: s for sid, s in state.sources.items()
            if s.retrieval_status == "success" and s.snippet
        }

        # Case 1: No evidence was gathered
        if not successful_sources:
            logger.warning("No successful sources found to synthesize answer.")
            state.final_answer = (
                "I couldn't gather reliable web evidence for this question. "
                "Please try again later, verify your network or API credentials, or use a more specific research question."
            )
            if state.status != "step_limit_reached":
                state.status = "failed"
            return

        # Prepare evidence text with explicit IDs
        evidence_blocks = []
        for sid, src in successful_sources.items():
            evidence_blocks.append(
                f"SOURCE ID: [{sid}]\n"
                f"TITLE: {src.title}\n"
                f"URL: {src.url}\n"
                f"CONTENT:\n{src.snippet}\n"
                f"{'-'*40}"
            )
        evidence_text = "\n\n".join(evidence_blocks)

        system_prompt = SYNTHESIS_SYSTEM_PROMPT.format(evidence_text=evidence_text)
        user_prompt = f"Question: {state.question}\n\nSynthesize an accurate, evidence-backed answer with inline citations."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            draft_answer = response.choices[0].message.content.strip()

            # Validate citations
            validation = CitationValidator.validate(draft_answer, state.sources)
            logger.info(f"Citation validation result: is_valid={validation.is_valid}, cited={validation.cited_ids}")

            # Controlled 1-time correction if validation failed
            if not validation.is_valid:
                logger.warning(f"Initial answer failed citation validation: {validation.error_message}. Attempting correction...")
                corrected_answer = self._attempt_correction(
                    draft_answer=draft_answer,
                    error_message=validation.error_message or "Invalid citations",
                    valid_ids=list(successful_sources.keys()),
                    evidence_text=evidence_text,
                    question=state.question,
                )
                if corrected_answer:
                    re_validation = CitationValidator.validate(corrected_answer, state.sources)
                    if re_validation.is_valid:
                        draft_answer = corrected_answer
                        validation = re_validation
                        logger.info("Citation correction succeeded!")
                    else:
                        logger.warning("Citation correction still failed. Appending safety advisory.")
                        draft_answer = (
                            f"> ⚠️ **Note**: Some claims in this answer could not be fully substantiated against the fetched sources.\n\n"
                            + draft_answer
                        )

            # Append clean Markdown Sources section if not already embedded
            sources_footer = CitationValidator.build_sources_section(
                sources=state.sources,
                cited_only=True,
                cited_ids=validation.cited_ids,
            )
            state.final_answer = draft_answer + sources_footer

        except OpenAIError as e:
            logger.error(f"OpenAI error during synthesis: {e}")
            state.add_error(f"Synthesis failed: {str(e)}")
            state.final_answer = (
                "An error occurred while synthesizing the answer from the retrieved evidence. "
                f"Error: {str(e)}"
            )
            state.status = "failed"
        except Exception as e:
            logger.error(f"Unexpected error during synthesis: {e}")
            state.add_error(f"Synthesis error: {str(e)}")
            state.final_answer = f"Unexpected synthesis error: {str(e)}"
            state.status = "failed"

    def _attempt_correction(
        self,
        draft_answer: str,
        error_message: str,
        valid_ids: list[str],
        evidence_text: str,
        question: str,
    ) -> Optional[str]:
        """Attempt one controlled regeneration of the answer fixing invalid citations."""
        try:
            correction_sys = CORRECTION_SYSTEM_PROMPT.format(
                validation_error=error_message,
                valid_source_ids=", ".join(valid_ids),
                evidence_text=evidence_text,
            )
            user_msg = (
                f"Original Question: {question}\n\n"
                f"Draft Answer with errors:\n{draft_answer}\n\n"
                f"Please produce a corrected version strictly adhering to the valid source IDs."
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": correction_sys},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Correction attempt failed: {e}")
            return None
