"""Reminders persistence API endpoints with sanitized error boundaries."""
import logging
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict, field_validator
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

def normalize_due_time(v: Optional[str]) -> Optional[str]:
    """Validates and normalizes reminder timestamps into ISO 8601 format."""
    if v is None:
        return None
    val = v.strip()
    if not val:
        raise ValueError("due_time cannot be empty")

    # 1. Try ISO 8601 parsing (supports timezone offsets and trailing Z)
    try:
        clean_iso = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        return dt.isoformat()
    except Exception:
        pass

    # 2. Try standard date-time representations
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            dt = datetime.strptime(val, fmt)
            return dt.isoformat()
        except ValueError:
            pass

    # 3. Try time-only format (combines with today's date for local convenience)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(val, fmt).time()
            dt = datetime.combine(date.today(), t)
            return dt.isoformat()
        except ValueError:
            pass

    raise ValueError(
        f"Invalid datetime format '{val}'. due_time must be a valid ISO 8601 timestamp (e.g. '2026-10-25T19:30:00Z', '2026-10-25T19:30:00') or 'HH:MM'."
    )

class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    due_time: str = Field(..., min_length=1, max_length=100)

    @field_validator("due_time")
    @classmethod
    def validate_due_time(cls, v: str) -> str:
        res = normalize_due_time(v)
        if not res:
            raise ValueError("due_time is required")
        return res

class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    due_time: Optional[str] = Field(None, min_length=1, max_length=100)
    completed: Optional[bool] = None

    @field_validator("due_time")
    @classmethod
    def validate_due_time(cls, v: Optional[str]) -> Optional[str]:
        return normalize_due_time(v)


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

@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
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
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to modify this reminder")

        if payload.title is not None:
            reminder.title = payload.title
        if payload.due_time is not None:
            reminder.due_time = payload.due_time
        if payload.completed is not None:
            reminder.completed = payload.completed

        await db.commit()
        await db.refresh(reminder)
        return ReminderResponse(
            id=reminder.id,
            title=reminder.title,
            due_time=reminder.due_time,
            completed=reminder.completed,
            user_id=reminder.user_id,
            created_at=reminder.created_at.isoformat() if reminder.created_at else ""
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to update reminder '{reminder_id}' for user '{user_id}': {e}", exc_info=True)
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
