"""JSON Schema definitions for LLM tool calling."""
from typing import Dict, Any, List

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "predict_ipl_match",
            "description": "Predict match win probabilities for an ongoing IPL 2nd innings run chase using the offline scikit-learn model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "batting_team": {"type": "string", "description": "Name of chasing team"},
                    "bowling_team": {"type": "string", "description": "Name of defending team"},
                    "city": {"type": "string", "description": "Match venue city"},
                    "target_score": {"type": "integer", "description": "Target score to chase"},
                    "current_score": {"type": "integer", "description": "Current runs scored by chasing team"},
                    "overs_completed": {"type": "integer", "description": "Completed overs bowled (0-20)"},
                    "balls_in_over": {"type": "integer", "description": "Additional balls bowled in current over (0-5)"},
                    "wickets_out": {"type": "integer", "description": "Wickets fallen (0-10)"}
                },
                "required": ["batting_team", "bowling_team", "city", "target_score", "current_score", "overs_completed", "wickets_out"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Add a new task or todo item to the user's persistent PostgreSQL database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The title or action description of the task"},
                    "category": {"type": "string", "description": "Category: general, work, personal", "default": "general"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Retrieve the current list of saved tasks from the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_completed": {"type": "boolean", "description": "Whether to include finished tasks", "default": False}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a new time-based reminder in the user's database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "What to remind the user about"},
                    "due_time": {"type": "string", "description": "Due time or date description (e.g. 19:30 or 2026-10-24 10:00)"}
                },
                "required": ["title", "due_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Retrieve active reminders from the database.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]
