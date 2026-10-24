"""Tool Registry: registers tool schemas and dispatches execution calls."""
import json
import logging
from typing import Dict, Any, Callable, Awaitable, List
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.tools.schemas import TOOL_SCHEMAS
from backend.app.tools.handlers import (
    handle_predict_ipl_match,
    handle_create_task,
    handle_list_tasks,
    handle_create_reminder,
    handle_list_reminders
)

logger = logging.getLogger(__name__)

ToolHandler = Callable[[Dict[str, Any], AsyncSession, str], Awaitable[Dict[str, Any]]]

class ToolRegistry:
    def __init__(self):
        self._handlers: Dict[str, ToolHandler] = {
            "predict_ipl_match": handle_predict_ipl_match,
            "create_task": handle_create_task,
            "list_tasks": handle_list_tasks,
            "create_reminder": handle_create_reminder,
            "list_reminders": handle_list_reminders
        }
        self.schemas = TOOL_SCHEMAS

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    async def execute(self, tool_name: str, arguments: Dict[str, Any], db: AsyncSession, user_id: str) -> Dict[str, Any]:
        """Safely executes a registered tool with error isolation."""
        if not self.has_tool(tool_name):
            logger.warning(f"Attempted execution of unknown tool: {tool_name}")
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' is not recognized or permitted in this system."
            }

        handler = self._handlers[tool_name]
        try:
            logger.info(f"Executing tool '{tool_name}' for user '{user_id}' with args: {arguments}")
            result = await handler(arguments, db, user_id)
            return result
        except Exception as e:
            logger.exception(f"Unhandled exception during tool execution '{tool_name}': {e}")
            return {
                "status": "error",
                "message": f"Tool execution failed: {str(e)}"
            }

tool_registry = ToolRegistry()
