"""Tool execution handlers providing concrete logic for assistant tool calls."""
import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.ml.ipl_pipeline import ipl_service
from backend.app.ml.schemas import IPLPredictionRequest
from backend.app.models.entities import TaskEntity, ReminderEntity, UserEntity

logger = logging.getLogger(__name__)

async def handle_predict_ipl_match(args: Dict[str, Any], db: AsyncSession, user_id: str) -> Dict[str, Any]:
    try:
        req = IPLPredictionRequest(**args)
        result = ipl_service.predict(req)
        return {
            "status": "success",
            "batting_team": result.batting_team,
            "bowling_team": result.bowling_team,
            "batting_win_probability": f"{result.batting_win_probability * 100:.1f}%",
            "bowling_win_probability": f"{result.bowling_win_probability * 100:.1f}%",
            "projected_winner": result.projected_winner,
            "summary": result.status_summary
        }
    except Exception as e:
        logger.error(f"IPL prediction tool execution failed: {type(e).__name__}", exc_info=True)
        return {"status": "error", "message": "Failed to compute IPL prediction. Please verify input match parameters."}

async def handle_create_task(args: Dict[str, Any], db: AsyncSession, user_id: str) -> Dict[str, Any]:
    title = args.get("title", "").strip()
    category = args.get("category", "general").strip()
    if not title:
        return {"status": "error", "message": "Task title cannot be empty."}

    try:
        if user_id:
            user = await db.get(UserEntity, user_id)
            if not user:
                user = UserEntity(id=user_id, username=user_id)
                db.add(user)
                await db.flush()

        task = TaskEntity(title=title, category=category, user_id=user_id)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return {"status": "success", "task_id": task.id, "title": task.title, "message": f"Created task: '{task.title}'"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to persist task for user '{user_id}': {type(e).__name__}", exc_info=True)
        return {"status": "error", "message": "Failed to persist task due to a storage error. Please retry."}

async def handle_list_tasks(args: Dict[str, Any], db: AsyncSession, user_id: str) -> Dict[str, Any]:
    try:
        stmt = select(TaskEntity).where(TaskEntity.user_id == user_id)
        if not args.get("include_completed", False):
            stmt = stmt.where(TaskEntity.completed == False)
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        return {
            "status": "success",
            "count": len(tasks),
            "tasks": [{"id": t.id, "title": t.title, "completed": t.completed} for t in tasks]
        }
    except Exception as e:
        logger.error(f"Failed to query tasks for user '{user_id}': {type(e).__name__}", exc_info=True)
        return {"status": "error", "message": "Failed to query tasks due to a storage error. Please retry."}

async def handle_create_reminder(args: Dict[str, Any], db: AsyncSession, user_id: str) -> Dict[str, Any]:
    title = args.get("title", "").strip()
    due_time = args.get("due_time", "").strip()
    if not title or not due_time:
        return {"status": "error", "message": "Title and due_time are required."}

    try:
        if user_id:
            user = await db.get(UserEntity, user_id)
            if not user:
                user = UserEntity(id=user_id, username=user_id)
                db.add(user)
                await db.flush()

        reminder = ReminderEntity(title=title, due_time=due_time, user_id=user_id)
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        return {"status": "success", "reminder_id": reminder.id, "message": f"Reminder scheduled for '{title}' at {due_time}."}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to persist reminder for user '{user_id}': {type(e).__name__}", exc_info=True)
        return {"status": "error", "message": "Failed to persist reminder due to a storage error. Please retry."}

async def handle_list_reminders(args: Dict[str, Any], db: AsyncSession, user_id: str) -> Dict[str, Any]:
    try:
        stmt = select(ReminderEntity).where(ReminderEntity.user_id == user_id)
        result = await db.execute(stmt)
        reminders = result.scalars().all()
        return {
            "status": "success",
            "count": len(reminders),
            "reminders": [{"id": r.id, "title": r.title, "due_time": r.due_time} for r in reminders]
        }
    except Exception as e:
        logger.error(f"Failed to query reminders for user '{user_id}': {type(e).__name__}", exc_info=True)
        return {"status": "error", "message": "Failed to query reminders due to a storage error. Please retry."}

