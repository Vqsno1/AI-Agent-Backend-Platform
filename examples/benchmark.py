"""Small mock-provider benchmark; not a model quality or production load test."""

import json
import os
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

count = int(os.getenv("BENCHMARK_TASKS", "10"))
concurrency = 2
with httpx.Client(
    base_url=os.getenv("API_URL", "http://localhost:8000"),
    headers={"X-API-Key": os.environ["API_KEY"]},
) as client:

    def run(index):
        start = time.monotonic()
        response = client.post(
            "/api/v1/tasks", json={"prompt": f"Compare Python frameworks sample {index}"}
        )
        response.raise_for_status()
        accepted = time.monotonic() - start
        task_id = response.json()["task_id"]
        while time.monotonic() - start < 150:
            response = client.get(f"/api/v1/tasks/{task_id}")
            response.raise_for_status()
            state = response.json()["status"]
            if state == "completed":
                return accepted, time.monotonic() - start
            if state in {"failed", "cancelled", "queue_failed"}:
                raise RuntimeError(state)
            time.sleep(0.05)
        raise TimeoutError(task_id)

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        timings = list(pool.map(run, range(count)))
    elapsed = time.monotonic() - start
    ordered = sorted(t[1] for t in timings)
    print(
        json.dumps(
            {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "logical_cpus_visible": os.cpu_count(),
                "tasks": count,
                "client_concurrency": concurrency,
                "provider": "mock (verify LLM_PROVIDER before running)",
                "elapsed_s": round(elapsed, 4),
                "completed_tasks_per_s": round(count / elapsed, 2),
                "post_median_ms": round(statistics.median(t[0] for t in timings) * 1000, 2),
                "completion_median_ms": round(statistics.median(ordered) * 1000, 2),
                "completion_p95_ms": round(
                    ordered[max(0, int(len(ordered) * 0.95 + 0.999) - 1)] * 1000, 2
                ),
            },
            indent=2,
        )
    )
