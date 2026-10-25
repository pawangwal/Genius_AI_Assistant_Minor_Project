"""Idempotent demonstration seed script for Tasks and Reminders.
Seeds 3 tasks and 2 reminders for the local development profile without duplicating records.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.entities import UserEntity, TaskEntity, ReminderEntity

DEMO_TASKS = [
    {
        "id": "demo-task-001",
        "title": "Review IPL win probability feature pipeline and calibration",
        "completed": False,
        "category": "ml",
    },
    {
        "id": "demo-task-002",
        "title": "Verify Faster-Whisper local voice transcription latency",
        "completed": True,
        "category": "voice",
    },
    {
        "id": "demo-task-003",
        "title": "Inspect PostgreSQL asyncpg persistence and connection pool",
        "completed": False,
        "category": "database",
    },
]

def get_demo_reminders():
    now = datetime.now()
    # Reminder 1: Due in 2 hours
    due_1 = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    # Reminder 2: Due tomorrow at 10 AM
    due_2 = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0).strftime("%Y-%m-%dT%H:%M")

    return [
        {
            "id": "demo-rem-001",
            "title": "Genius Assistant portfolio demo walkthrough",
            "due_time": due_1,
            "completed": False,
        },
        {
            "id": "demo-rem-002",
            "title": "Check live CricAPI match ticker and commentary feed",
            "due_time": due_2,
            "completed": False,
        },
    ]

async def seed_demo_data():
    async with AsyncSessionLocal() as session:
        # 1. Ensure local-user exists
        user_res = await session.execute(select(UserEntity).where(UserEntity.id == "local-user"))
        user = user_res.scalar_one_or_none()
        if not user:
            user = UserEntity(id="local-user", username="local_developer")
            session.add(user)
            await session.flush()
            print("[Seed] Created local-user")

        # 2. Seed Tasks idempotently
        tasks_seeded = 0
        for t_info in DEMO_TASKS:
            existing = await session.execute(select(TaskEntity).where(TaskEntity.id == t_info["id"]))
            if not existing.scalar_one_or_none():
                task = TaskEntity(
                    id=t_info["id"],
                    title=t_info["title"],
                    completed=t_info["completed"],
                    category=t_info["category"],
                    user_id="local-user"
                )
                session.add(task)
                tasks_seeded += 1

        # 3. Seed Reminders idempotently
        reminders_seeded = 0
        for r_info in get_demo_reminders():
            existing = await session.execute(select(ReminderEntity).where(ReminderEntity.id == r_info["id"]))
            if not existing.scalar_one_or_none():
                rem = ReminderEntity(
                    id=r_info["id"],
                    title=r_info["title"],
                    due_time=r_info["due_time"],
                    completed=r_info["completed"],
                    user_id="local-user"
                )
                session.add(rem)
                reminders_seeded += 1

        await session.commit()
        print(f"[Seed] Done: {tasks_seeded} tasks and {reminders_seeded} reminders seeded.")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
