"""Reminders persistence API endpoints with sanitized error boundaries."""
import logging
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user_id
from backend.app.models.entities import ReminderEntity, UserEntity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reminders", tags=["Reminders"])

DATABASE_ERROR_MESSAGE = "Database service unavailable. Downstream storage is degraded."

class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    due_time: str = Field(..., min_length=1, max_length=100)

class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    due_time: str
    completed: bool
    user_id: Optional[str]
    created_at: str

@router.get("", response_model=List[ReminderResponse])
async def list_reminders(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        stmt = select(ReminderEntity).where(ReminderEntity.user_id == user_id).order_by(ReminderEntity.created_at.desc())
        result = await db.execute(stmt)
        reminders = result.scalars().all()
        return [
            ReminderResponse(
                id=r.id,
                title=r.title,
                due_time=r.due_time,
                completed=r.completed,
                user_id=r.user_id,
                created_at=r.created_at.isoformat() if r.created_at else ""
            ) for r in reminders
        ]
    except SQLAlchemyError as e:
        logger.error(f"Failed to query reminders for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )

@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    payload: ReminderCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        if user_id:
            user = await db.get(UserEntity, user_id)
            if not user:
                user = UserEntity(id=user_id, username=user_id)
                db.add(user)
                await db.flush()

        new_reminder = ReminderEntity(
            title=payload.title,
            due_time=payload.due_time,
            user_id=user_id
        )
        db.add(new_reminder)
        await db.commit()
        await db.refresh(new_reminder)
        return ReminderResponse(
            id=new_reminder.id,
            title=new_reminder.title,
            due_time=new_reminder.due_time,
            completed=new_reminder.completed,
            user_id=new_reminder.user_id,
            created_at=new_reminder.created_at.isoformat() if new_reminder.created_at else ""
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to create reminder for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )

@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        stmt = select(ReminderEntity).where(ReminderEntity.id == reminder_id)
        result = await db.execute(stmt)
        reminder = result.scalar_one_or_none()
        if not reminder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
        if reminder.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete this reminder")

        await db.delete(reminder)
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to delete reminder '{reminder_id}' for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )
