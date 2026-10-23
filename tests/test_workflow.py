import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.db.models import Memory, Task, TaskStep, ToolExecution
from app.llm.client import AgentOutput, LLMClient
from app.services.execution_service import execute_task
from app.tools.registry import ToolRegistry

PAYLOAD = {"prompt": "Compare Python backend frameworks"}


def submit(api):
    response = api.post("/api/v1/tasks", json=PAYLOAD)
    assert response.status_code == 202
    return response.json()["task_id"]


def test_complete_and_duplicate(api, db_factory):
    task_id = submit(api)
    execute_task(task_id)
    execute_task(task_id)
    response = api.get(f"/api/v1/tasks/{task_id}").json()
    assert response["status"] == "completed"
    assert "Mock" in response["result"]["summary"]
    steps = api.get(f"/api/v1/tasks/{task_id}/steps").json()
    assert [s["agent_type"] for s in steps] == ["planner", "research", "analyst", "summarizer"]
    assert all(s["attempts"] == 1 and s["status"] == "completed" for s in steps)
    assert len(api.post("/api/v1/memories/search", json={"query": "Mock"}).json()) == 1
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_isolation_and_auth(api):
    task_id = submit(api)
    execute_task(task_id)
    api.headers["X-API-Key"] = "test-bob"
    for suffix in ("", "/steps"):
        assert api.get(f"/api/v1/tasks/{task_id}{suffix}").status_code == 404
    assert api.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 404
    assert api.get("/api/v1/tasks").json() == []
    assert api.post("/api/v1/memories/search", json={"query": "Mock"}).json() == []
    api.headers.clear()
    assert api.get("/api/v1/tasks").status_code == 401


def test_cancel_pending(api):
    task_id = submit(api)
    assert api.post(f"/api/v1/tasks/{task_id}/cancel").json()["status"] == "cancelled"
    execute_task(task_id)
    assert api.get(f"/api/v1/tasks/{task_id}/steps").json() == []


def test_cancel_running(api):
    task_id = submit(api)

    class CancelClient(LLMClient):
        def generate_structured(self, role, context):
            assert api.post(f"/api/v1/tasks/{task_id}/cancel").json()["status"] == "cancelling"
            return super().generate_structured(role, context)

    execute_task(task_id, CancelClient())
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "cancelled"


def test_retry_failure(api):
    task_id = submit(api)

    class Broken:
        calls = 0

        def generate_structured(self, role, context):
            self.calls += 1
            raise RuntimeError("secret must not leak")

    client = Broken()
    execute_task(task_id, client)
    assert client.calls == 3
    response = api.get(f"/api/v1/tasks/{task_id}")
    assert response.json()["status"] == "failed"
    assert "secret" not in response.text


def test_transient_retry_and_tool_audit(api, db_factory):
    task_id = submit(api)

    class Flaky(LLMClient):
        failed = False

        def generate_structured(self, role, context):
            if not self.failed:
                self.failed = True
                raise RuntimeError("temporary")
            if role == "research":
                return AgentOutput(
                    summary="Calculation",
                    tool_calls=[{"name": "calculator", "arguments": {"expression": "(2+3)*4"}}],
                )
            return super().generate_structured(role, context)

    execute_task(task_id, Flaky())
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "completed"
    with db_factory() as db:
        tool = db.scalar(select(ToolExecution))
        assert tool.status == "completed"
        step = db.scalar(select(TaskStep).where(TaskStep.agent_type == "research"))
        assert "20" in str(step.output)


@pytest.mark.parametrize(
    "expression", ["__import__('os').getcwd()", "2**1000", "1/0", "[1,2]", "1e20"]
)
def test_calculator_rejects_code(expression):
    with pytest.raises((ValueError, ZeroDivisionError)):
        ToolRegistry().execute("calculator", {"expression": expression}, {"calculator"})


def test_tool_permissions():
    with pytest.raises(ValueError, match="tool_not_allowed"):
        ToolRegistry().execute("calculator", {"expression": "2+2"}, set())


def test_validation(api):
    for payload in (
        {"prompt": " "},
        {"prompt": "x", "max_steps": 3},
        {"prompt": "x", "workflow": "arbitrary"},
    ):
        assert api.post("/api/v1/tasks", json=payload).status_code == 422


def test_queue_failure(api, monkeypatch):
    def fail(**kwargs):
        raise ConnectionError()

    monkeypatch.setattr("app.main.run_task.apply_async", fail)
    response = api.post("/api/v1/tasks", json=PAYLOAD)
    assert response.status_code == 503
    task_id = response.json()["detail"]["task_id"]
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "queue_failed"


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="PostgreSQL concurrency test")
def test_concurrent_duplicate_delivery(api, db_factory):
    task_id = submit(api)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(execute_task, [task_id, task_id]))
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "completed"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(TaskStep)) == 4
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_budget_enforced_before_provider_call(api, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "task_budget_usd", 0.000001)
    task_id = submit(api)

    class NeverCalled:
        def generate_structured(self, role, context):
            pytest.fail("Provider called after budget exhaustion")

    execute_task(task_id, NeverCalled())
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "failed"


def test_interrupted_worker_resumes_completed_steps(api, db_factory):
    task_id = submit(api)
    with db_factory() as db:
        task = db.get(Task, task_id)
        task.status = "running"
        db.add(
            TaskStep(
                task_id=task_id,
                agent_type="planner",
                step_order=0,
                attempts=1,
                status="completed",
                output=AgentOutput(summary="Saved planner output").model_dump(),
            )
        )
        db.commit()

    class Resume(LLMClient):
        def generate_structured(self, role, context):
            assert role != "planner", "Completed step was rerun"
            return super().generate_structured(role, context)

    execute_task(task_id, Resume())
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "completed"


def test_no_memory_when_disabled(api, db_factory):
    task_id = api.post("/api/v1/tasks", json={**PAYLOAD, "use_memory": False}).json()["task_id"]
    execute_task(task_id)
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 0


def test_unauthorized_tool_is_audited(api, db_factory):
    task_id = submit(api)

    class Unsafe:
        def generate_structured(self, role, context):
            return AgentOutput(summary="Unsafe", tool_calls=[{"name": "shell", "arguments": {}}])

    execute_task(task_id, Unsafe())
    assert api.get(f"/api/v1/tasks/{task_id}").json()["status"] == "failed"
    with db_factory() as db:
        records = db.scalars(select(ToolExecution)).all()
        assert len(records) == 3
        assert all(r.status == "failed" and r.error_code == "tool_rejected" for r in records)


def test_malformed_provider_output_retries(api):
    from pydantic import ValidationError

    task_id = submit(api)

    class Malformed:
        def generate_structured(self, role, context):
            return AgentOutput.model_validate_json('{"summary": 42}')

    execute_task(task_id, Malformed())
    result = api.get(f"/api/v1/tasks/{task_id}").json()
    assert result["status"] == "failed" and result["error_code"] == ValidationError.__name__
    assert api.get(f"/api/v1/tasks/{task_id}/steps").json()[0]["attempts"] == 3


def test_deadline_stops_pipeline(api, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "task_timeout", -1)
    task_id = submit(api)
    execute_task(task_id)
    result = api.get(f"/api/v1/tasks/{task_id}").json()
    assert result["status"] == "failed" and result["error_code"] == "TimeoutError"


def test_non_ascii_invalid_api_key_returns_unauthorized():
    from fastapi import HTTPException

    from app.dependencies import current_user

    with pytest.raises(HTTPException) as error:
        current_user("invalid-\u00e9-key")
    assert error.value.status_code == 401
