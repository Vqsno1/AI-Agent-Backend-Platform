"""Submit two tasks and wait for real worker results. Requires API_KEY in environment."""

import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

with httpx.Client(
    base_url=os.getenv("API_URL", "http://localhost:8000"),
    headers={"X-API-Key": os.environ["API_KEY"]},
) as client:

    def submit(prompt):
        response = client.post("/api/v1/tasks", json={"prompt": prompt})
        response.raise_for_status()
        return response.json()["task_id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(submit, ["Compare FastAPI, Django and Flask", "Analyze async Python APIs"])
        )
    deadline = time.monotonic() + 150
    remaining = set(ids)
    while remaining and time.monotonic() < deadline:
        for task_id in list(remaining):
            response = client.get(f"/api/v1/tasks/{task_id}")
            response.raise_for_status()
            task = response.json()
            if task["status"] in {"completed", "failed", "cancelled", "queue_failed"}:
                print(task)
                assert task["status"] == "completed", task
                steps = client.get(f"/api/v1/tasks/{task_id}/steps").json()
                assert len(steps) == 4 and all(s["status"] == "completed" for s in steps)
                remaining.remove(task_id)
        if remaining:
            time.sleep(0.25)
    assert not remaining, "Worker did not complete tasks in time"
