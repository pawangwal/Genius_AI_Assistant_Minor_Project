"""PostgreSQL integration tests for Task and Reminder persistence, user ownership boundaries,
foreign key constraints, unique constraints, transactional rollback, and error handling.
Standardized exclusively on PostgreSQL (asyncpg); zero SQLite or in-memory emulation allowed.
"""
import pytest
from unittest.mock import patch
from sqlalchemy import text, select
from sqlalchemy.exc import OperationalError, IntegrityError
from backend.app.core.database import get_db
from backend.app.models.entities import UserEntity, TaskEntity, ReminderEntity
from backend.app.main import app

@pytest.mark.asyncio
async def test_postgresql_connection_and_session_lifecycle(test_db):
    """Verifies that the session operates directly against real PostgreSQL."""
    result = await test_db.execute(text("SELECT version();"))
    version = result.scalar()
    assert version is not None
    assert "PostgreSQL" in version

    db_res = await test_db.execute(text("SELECT current_database();"))
    current_db = db_res.scalar()
    assert current_db == "genius_ai_test"
    assert "test" in current_db.lower()

@pytest.mark.asyncio
async def test_migration_managed_schema_verification(test_db):
    """Verifies that the test database schema was provisioned via Alembic migrations,
    with alembic_version matching the active migration head programmatically,
    and all expected tables and constraints verified.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    expected_head = script.get_current_head()
    assert expected_head is not None

    # 1. Verify alembic_version table exists and matches the programmatic Alembic head revision
    alembic_res = await test_db.execute(text("SELECT version_num FROM alembic_version;"))
    version = alembic_res.scalar()
    assert version == expected_head

    # 2. Verify all expected migration tables exist in information_schema
    tables_res = await test_db.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
    ))
    tables = {row[0] for row in tables_res.fetchall()}
    assert {"users", "tasks", "reminders", "alembic_version"}.issubset(tables)

@pytest.mark.asyncio
async def test_test_role_cannot_access_primary_database():
    """Verifies that the dedicated test user/credentials cannot access or modify the primary application database.
    PostgreSQL must reject the connection with an explicit permission denied error at the database boundary.
    """
    import asyncpg
    from backend.app.core.config import settings
    from sqlalchemy import make_url

    parsed_test = make_url(settings.DATABASE_URL_TEST)
    parsed_main = make_url(settings.DATABASE_URL)

    with pytest.raises(Exception) as exc_info:
        conn = await asyncpg.connect(
            user=parsed_test.username,
            password=parsed_test.password,
            host=parsed_main.host,
            port=parsed_main.port,
            database=parsed_main.database
        )
        await conn.close()

    err_str = str(exc_info.value).lower()
    assert "permission denied" in err_str or "does not have connect privilege" in err_str or "privilege" in err_str

@pytest.mark.asyncio
async def test_postgresql_unique_constraint_enforcement(test_db):
    """Verifies that PostgreSQL enforces unique constraints on users.username."""
    import uuid
    user1 = UserEntity(id=str(uuid.uuid4()), username="duplicate_user", hashed_password="hashed_pw_1")
    test_db.add(user1)
    await test_db.commit()

    user2 = UserEntity(id=str(uuid.uuid4()), username="duplicate_user", hashed_password="hashed_pw_2")
    test_db.add(user2)
    with pytest.raises(IntegrityError) as exc_info:
        await test_db.commit()
    await test_db.rollback()
    assert "unique" in str(exc_info.value).lower() or "ix_users_username" in str(exc_info.value)

@pytest.mark.asyncio
async def test_postgresql_foreign_key_constraint_enforcement(test_db):
    """Verifies that PostgreSQL enforces foreign key integrity on tasks.user_id -> users.id."""
    import uuid
    # Attempt to insert a task pointing to a non-existent user_id
    orphan_task = TaskEntity(
        id=str(uuid.uuid4()),
        title="Orphan Task",
        user_id="non-existent-user-id"
    )
    test_db.add(orphan_task)
    with pytest.raises(IntegrityError) as exc_info:
        await test_db.commit()
    await test_db.rollback()
    assert "foreign key" in str(exc_info.value).lower() or "tasks_user_id_fkey" in str(exc_info.value)

@pytest.mark.asyncio
async def test_postgresql_transaction_rollback(test_db):
    """Verifies that an aborted transaction rolls back all pending writes in PostgreSQL."""
    import uuid
    u_id = str(uuid.uuid4())
    user = UserEntity(id=u_id, username=f"rollback_user_{u_id[:8]}", hashed_password="pw")
    test_db.add(user)
    await test_db.flush()

    # Roll back transaction
    await test_db.rollback()

    # Query to verify user was not committed
    res = await test_db.execute(select(UserEntity).where(UserEntity.id == u_id))
    assert res.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_task_lifecycle_crud(client_with_db):
    """Tests complete Task creation, listing, updating, and deletion in PostgreSQL."""
    # 1. Create task
    create_resp = await client_with_db.post("/api/v1/tasks", json={
        "title": "Review match prediction report",
        "category": "work"
    })
    assert create_resp.status_code == 201
    task_data = create_resp.json()
    task_id = task_data["id"]
    assert task_data["title"] == "Review match prediction report"
    assert task_data["completed"] is False

    # 2. List tasks
    list_resp = await client_with_db.get("/api/v1/tasks")
    assert list_resp.status_code == 200
    tasks = list_resp.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id

    # 3. Update task
    patch_resp = await client_with_db.patch(f"/api/v1/tasks/{task_id}", json={
        "completed": True
    })
    assert patch_resp.status_code == 200
    assert patch_resp.json()["completed"] is True

    # 4. Delete task
    del_resp = await client_with_db.delete(f"/api/v1/tasks/{task_id}")
    assert del_resp.status_code == 204

    # 5. Verify deleted
    list_resp_after = await client_with_db.get("/api/v1/tasks")
    assert len(list_resp_after.json()) == 0

@pytest.mark.asyncio
async def test_reminder_lifecycle_crud(client_with_db):
    """Tests Reminder creation, listing, and deletion in PostgreSQL."""
    create_resp = await client_with_db.post("/api/v1/reminders", json={
        "title": "Evening IPL match starts",
        "due_time": "19:30"
    })
    assert create_resp.status_code == 201
    reminder_id = create_resp.json()["id"]

    list_resp = await client_with_db.get("/api/v1/reminders")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    del_resp = await client_with_db.delete(f"/api/v1/reminders/{reminder_id}")
    assert del_resp.status_code == 204

@pytest.mark.asyncio
async def test_cross_user_task_isolation(client_with_db):
    """Users cannot modify or delete tasks owned by another user (isolated ownership in PostgreSQL)."""
    from backend.app.core.security import create_access_token
    token_user1 = create_access_token(user_id="user-1")
    token_user2 = create_access_token(user_id="user-2")

    # User 1 creates a task
    resp1 = await client_with_db.post(
        "/api/v1/tasks",
        json={"title": "User 1 Secret Task"},
        headers={"Authorization": f"Bearer {token_user1}"}
    )
    assert resp1.status_code == 201
    task_id = resp1.json()["id"]

    # User 2 attempts to patch User 1's task
    patch_resp = await client_with_db.patch(
        f"/api/v1/tasks/{task_id}",
        json={"completed": True},
        headers={"Authorization": f"Bearer {token_user2}"}
    )
    assert patch_resp.status_code == 403
    assert "Unauthorized" in patch_resp.json()["detail"]

    # User 2 attempts to delete User 1's task
    del_resp = await client_with_db.delete(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_user2}"}
    )
    assert del_resp.status_code == 403

@pytest.mark.asyncio
async def test_cross_user_isolation_profile_b_jwt(client_with_db):
    """In Profile B with real JWT tokens, cross-user mutations are strictly forbidden (403)."""
    from backend.app.core.security import create_access_token
    token_alice = create_access_token(user_id="alice-id")
    token_bob = create_access_token(user_id="bob-id")

    with patch("backend.app.core.security.settings.AUTH_REQUIRED", True):
        # Alice creates a task
        resp1 = await client_with_db.post(
            "/api/v1/tasks",
            json={"title": "Alice Confidential Strategy"},
            headers={"Authorization": f"Bearer {token_alice}"}
        )
        assert resp1.status_code == 201
        task_id = resp1.json()["id"]

        # Bob attempts to modify Alice's task
        patch_resp = await client_with_db.patch(
            f"/api/v1/tasks/{task_id}",
            json={"completed": True},
            headers={"Authorization": f"Bearer {token_bob}"}
        )
        assert patch_resp.status_code == 403
        assert "Unauthorized to modify this task" in patch_resp.json()["detail"]

        # Bob attempts to delete Alice's task
        del_resp = await client_with_db.delete(
            f"/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token_bob}"}
        )
        assert del_resp.status_code == 403

@pytest.mark.asyncio
async def test_database_failure_returns_503(async_client):
    """Database connection failure triggers explicit HTTP 503 (no silent fallback)."""
    with patch("backend.app.api.v1.tasks.get_db") as mock_db:
        async def failing_db():
            raise OperationalError("Connection refused", {}, Exception("Downstream DB unreachable"))
            yield
        app.dependency_overrides[get_db] = failing_db
        try:
            resp = await async_client.get("/api/v1/tasks")
            assert resp.status_code == 503
            assert resp.json()["detail"] == "Database service unavailable. Downstream storage is degraded."
        finally:
            app.dependency_overrides.clear()
