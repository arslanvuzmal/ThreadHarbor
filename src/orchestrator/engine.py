import json

from src.bot.models import BotResponse, Role, SessionState
from src.bot.session import SessionManager
from src.intelligence.context import ContextBuilder
from src.intelligence.llm_client import LLMClient
from src.intelligence.rag import RAGPipeline
from src.intelligence.tools import TOOL_DEFINITIONS, execute_tool
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Manages state transitions, combining RAG context, context windows, and tool completions."""

    def __init__(
        self,
        session_manager: SessionManager,
        llm_client: LLMClient,
        rag_pipeline: RAGPipeline,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        """Initialize Orchestrator with dependencies."""
        self.session_manager = session_manager
        self.llm_client = llm_client
        self.rag_pipeline = rag_pipeline
        self.context_builder = context_builder or ContextBuilder()

    async def process_message(self, session_id: str, user_input: str) -> BotResponse:
        """Processes user input through RAG, Context formatting, and an async tool-completion loop.

        Args:
            session_id: The ID of the session.
            user_input: The raw user message string.

        Returns:
            A BotResponse representing the assistant's final response text.
        """
        try:
            # 1. Fetch current session
            session = await self.session_manager.get_or_create_session(session_id)

            # Handle handoff bypass
            if session.state == SessionState.HUMAN_HANDOFF:
                logger.info("Bypassing bot response, session in HUMAN_HANDOFF state", session_id=session_id)
                return BotResponse(
                    text="Thank you for reaching out. A human representative will assist you shortly.",
                    buttons=None,
                    should_escalate=False,
                )

            # 2. Save user message immediately and transition to PROCESSING
            await self.session_manager.add_message(session_id, Role.USER, user_input)
            session = await self.session_manager.get_or_create_session(session_id)

            # Transition state to PROCESSING and persist state immediately
            old_state = session.state
            session.state = SessionState.PROCESSING
            await self.session_manager.update_session(session)
            logger.info(
                "Session state transition",
                session_id=session_id,
                from_state=old_state.name,
                to_state=session.state.name,
            )

            # 3. Retrieve relevant context blocks using RAG pipeline
            rag_docs = await self.rag_pipeline.retrieve_context(user_input, top_k=3)
            if rag_docs:
                rag_context = "\n".join([doc.get("text", "") for doc in rag_docs])
            else:
                rag_context = "No knowledge base documents matching."

            # 4. Construct prompts templates utilizing the context builder
            messages = self.context_builder.build_messages(session.history, rag_context)

            # 5. Agentic loop with tool resolution
            llm_response = await self.llm_client.chat_completion(messages, tools=TOOL_DEFINITIONS)
            finish_reason = llm_response.get("finish_reason", "stop")
            llm_message = llm_response.get("message", {})

            loop_limit = 5
            loop_count = 0
            did_initiate_refund = False
            refund_amount = 0.0

            while finish_reason == "tool_calls" and loop_count < loop_limit:
                loop_count += 1
                tool_calls = llm_message.get("tool_calls", [])
                logger.info("LLM requested tool executions", tool_calls_count=len(tool_calls), session_id=session_id)

                messages.append(llm_message)

                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    func_details = tc.get("function", {})
                    func_name = func_details.get("name", "")
                    func_args_str = func_details.get("arguments", "{}")

                    # Parse JSON arguments safely
                    try:
                        func_args = json.loads(func_args_str)
                    except Exception:
                        func_args = {}

                    if func_name == "initiate_refund":
                        did_initiate_refund = True
                        try:
                            refund_amount = float(func_args.get("amount", 0.0))
                        except (ValueError, TypeError):
                            refund_amount = 0.0

                    try:
                        tool_result = execute_tool(func_name, func_args)
                    except Exception as e:
                        logger.error("Tool execution failed", tool=func_name, error=str(e))
                        tool_result = f"Error: Tool execution failed with error {e!s}"

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": func_name,
                            "content": tool_result,
                        }
                    )

                llm_response = await self.llm_client.chat_completion(messages, tools=TOOL_DEFINITIONS)
                finish_reason = llm_response.get("finish_reason", "stop")
                llm_message = llm_response.get("message", {})

            final_text = llm_message.get("content") or ""

            # 6. Evaluate Escalation policies
            should_escalate = False
            if "[ESCALATE]" in final_text or (did_initiate_refund and refund_amount > 500.0):
                should_escalate = True
                session.state = SessionState.ESCALATED
                logger.info(
                    "Session escalated to human handoff",
                    session_id=session_id,
                    refund_trigger=did_initiate_refund,
                    refund_amount=refund_amount,
                )
                final_text = final_text.replace("[ESCALATE]", "").strip()
            else:
                session.state = SessionState.AWAITING_INPUT

            # Persist bot reply and final state details
            await self.session_manager.add_message(session_id, Role.BOT, final_text)

            session = await self.session_manager.get_or_create_session(session_id)
            session.state = SessionState.ESCALATED if should_escalate else SessionState.AWAITING_INPUT
            await self.session_manager.update_session(session)

            logger.info(
                "Session state transition",
                session_id=session_id,
                from_state="PROCESSING",
                to_state=session.state.name,
            )

            return BotResponse(
                text=final_text,
                buttons=None,
                should_escalate=should_escalate,
            )

        except Exception as e:
            logger.exception("An unhandled exception occurred in the Orchestrator loop", session_id=session_id, error=str(e))  # noqa: E501
            # Graceful fallback response
            fallback_text = (
                "I'm having trouble connecting to my knowledge base. "
                "Let me get a human representative to assist you."
            )
            return BotResponse(
                text=fallback_text,
                buttons=None,
                should_escalate=True,
            )

    async def handle_agent_reply(self, session_id: str, agent_message: str) -> BotResponse:
        """Process a reply sent by a human agent back to the user.

        Transitions state based on agent action or keeps HUMAN_HANDOFF active.

        Args:
            session_id: The ID of the session.
            agent_message: The message sent by the agent.

        Returns:
            A BotResponse containing the agent's reply.
        """
        # Fetch current state
        session = await self.session_manager.get_or_create_session(session_id)

        # Determine next state
        old_state = session.state
        if "close" in agent_message.lower() or "resolve" in agent_message.lower():
            session.state = SessionState.AWAITING_INPUT
        else:
            session.state = SessionState.HUMAN_HANDOFF

        logger.info(
            "Agent message transition",
            session_id=session_id,
            from_state=old_state.name,
            to_state=session.state.name,
        )

        # Save session state changes
        await self.session_manager.update_session(session)

        # Add the agent message to history
        await self.session_manager.add_message(session_id, Role.SYSTEM, f"Agent: {agent_message}")

        return BotResponse(
            text=agent_message,
            buttons=None,
            should_escalate=False,
        )
