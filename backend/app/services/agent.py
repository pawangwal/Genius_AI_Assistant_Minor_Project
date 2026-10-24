"""Bounded agent orchestration loop coordinating LLM provider with validated tool registry."""
import json
import logging
from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.services.openrouter_provider import openrouter_provider, LLMError, LLMConnectionError
from backend.app.services.ollama_provider import ollama_provider, OllamaError, OllamaConnectionError
from backend.app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Genius, a brilliant, helpful, and secure AI assistant created for Pawan Sir.
You can communicate fluently in both English and Hindi.
- If the user asks in Hindi, reply completely in Hindi (Devanagari script).
- If the user asks in English, reply in English.
- Keep your answers concise, accurate, and professional.

You have access to the following local tools:
1. predict_ipl_match: Predict match win probabilities for IPL run chases.
2. create_task: Add a task to the user's persistent PostgreSQL database.
3. list_tasks: Retrieve current tasks from the database.
4. create_reminder: Schedule a persistent reminder.
5. list_reminders: Retrieve scheduled reminders.

Use these tools when appropriate. Once you receive tool output, summarize the result clearly to the user.
"""

def get_active_llm_provider():
    """Resolves the configured AI provider (OpenRouter or local Ollama)."""
    if settings.LLM_PROVIDER.lower() == "ollama":
        return ollama_provider
    return openrouter_provider

class AgentOrchestrator:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations

    async def run_stream(
        self,
        messages: List[Dict[str, Any]],
        db: AsyncSession,
        user_id: str
    ) -> AsyncGenerator[str, None]:
        """Executes the bounded tool-calling loop and yields SSE-formatted events."""
        provider = get_active_llm_provider()

        # Ensure system prompt is present
        convo = [{"role": "system", "content": SYSTEM_PROMPT}] + [
            m for m in messages if m.get("role") != "system"
        ]

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Agent reasoning iteration {iteration}/{self.max_iterations} using {provider.__class__.__name__}")

            try:
                # Non-streaming step to check if tool call is emitted
                response = await provider.chat(
                    messages=convo,
                    tools=tool_registry.schemas,
                    stream=False
                )
            except (LLMConnectionError, OllamaConnectionError) as e:
                logger.warning(f"Agent connection error: {type(e).__name__}")
                yield f"event: error\ndata: {json.dumps({'error': 'AI provider service is unreachable. Please verify network connectivity.'})}\n\n"
                return
            except (LLMError, OllamaError) as e:
                logger.error(f"Agent inference error: {type(e).__name__}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                return
            except Exception:
                logger.exception("Unexpected error in agent loop")
                yield f"event: error\ndata: {json.dumps({'error': 'An internal error occurred while processing your request.'})}\n\n"
                return

            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])

            # Case A: Model wants to invoke one or more tools
            if tool_calls:
                convo.append(message)
                for tool_call in tool_calls:
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    raw_args = func.get("arguments", {})
                    call_id = tool_call.get("id", f"call_{tool_name}")

                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            args = {}
                    else:
                        args = raw_args

                    # Emit SSE tool_call event
                    yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'args': args})}\n\n"

                    # Execute safely through validated registry
                    result = await tool_registry.execute(tool_name, args, db, user_id)

                    # Emit SSE tool_result event
                    yield f"event: tool_result\ndata: {json.dumps({'tool': tool_name, 'result': result})}\n\n"

                    # Append tool result into conversation history for the next iteration (OpenAI standard)
                    convo.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": json.dumps(result)
                    })

                # Loop continues to next iteration so model can formulate natural language response
                continue

            # Case B: Model returned direct text response (no more tool calls)
            content = message.get("content", "")
            # Yield token events for UI display
            chunk_size = 20
            for i in range(0, len(content), chunk_size):
                token_chunk = content[i:i+chunk_size]
                yield f"event: token\ndata: {json.dumps({'text': token_chunk})}\n\n"

            yield f"event: done\ndata: {json.dumps({'status': 'completed', 'total_iterations': iteration})}\n\n"
            return

        # Iteration cap reached
        warning_msg = "Notice: Maximum tool execution iterations reached for this request."
        yield f"event: token\ndata: {json.dumps({'text': warning_msg})}\n\n"
        yield f"event: done\ndata: {json.dumps({'status': 'max_iterations_reached'})}\n\n"

agent_orchestrator = AgentOrchestrator(max_iterations=settings.OLLAMA_MAX_ITERATIONS)
