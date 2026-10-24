"""Tasks persistence API endpoints with sanitized error boundaries."""
import logging
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user_id
from backend.app.models.entities import TaskEntity, UserEntity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

DATABASE_ERROR_MESSAGE = "Database service unavailable. Downstream storage is degraded."

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: str = Field("general", max_length=50)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    completed: Optional[bool] = None

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    completed: bool
    category: str
    user_id: Optional[str]
    created_at: str

@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        stmt = select(TaskEntity).where(TaskEntity.user_id == user_id).order_by(TaskEntity.created_at.desc())
        result = await db.execute(stmt)
        tasks = result.scalars().all()
        return [
            TaskResponse(
                id=t.id,
                title=t.title,
                completed=t.completed,
                category=t.category,
                user_id=t.user_id,
                created_at=t.created_at.isoformat() if t.created_at else ""
            ) for t in tasks
        ]
    except SQLAlchemyError as e:
        logger.error(f"Failed to query tasks for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
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

        new_task = TaskEntity(
            title=payload.title,
            category=payload.category,
            user_id=user_id
        )
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
        return TaskResponse(
            id=new_task.id,
            title=new_task.title,
            completed=new_task.completed,
            category=new_task.category,
            user_id=new_task.user_id,
            created_at=new_task.created_at.isoformat() if new_task.created_at else ""
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to create task for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        stmt = select(TaskEntity).where(TaskEntity.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if task.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to modify this task")

        if payload.title is not None:
            task.title = payload.title
        if payload.completed is not None:
            task.completed = payload.completed

        await db.commit()
        await db.refresh(task)
        return TaskResponse(
            id=task.id,
            title=task.title,
            completed=task.completed,
            category=task.category,
            user_id=task.user_id,
            created_at=task.created_at.isoformat() if task.created_at else ""
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to update task '{task_id}' for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        stmt = select(TaskEntity).where(TaskEntity.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if task.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to delete this task")

        await db.delete(task)
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(f"Failed to delete task '{task_id}' for user '{user_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DATABASE_ERROR_MESSAGE
        )
