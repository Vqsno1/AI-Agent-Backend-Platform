# Validation record

Initially validated on 2026-10-22; revalidated before publication on 2026-10-24 (Asia/Shanghai) in the development cloud environment.

| Check | Outcome |
| --- | --- |
| Frozen uv dependency install | Passed; 53 locked packages, 51 installed including development tools |
| Ruff lint and formatting | Passed |
| PostgreSQL behavior tests | 24 passed; no skips |
| SQLite portability tests | 23 passed; PostgreSQL concurrency test skipped |
| Alembic upgrade and metadata check | Passed; no pending schema changes |
| Host API + PostgreSQL + Redis + two-process Celery worker | Two concurrent tasks completed and saved four stages each |
| Docker image build | Passed with verification enabled and build-only cloud CA mount |
| Full Compose deployment | PostgreSQL/Redis healthy, migration succeeded, API ready; task demo passed |
| Compose worker restart | New queued tasks completed after worker restart |
| OpenAI-compatible HTTP contract | MockTransport test passed; no paid live-provider request made |
| Hosted GitHub Actions | Configuration added; not observed running remotely |

The test suite covers task and memory isolation, authentication, request validation, pending and running cancellation, transient retries, terminal retry failure, tool permission enforcement and audit records, calculator code rejection, malformed model output, deadline and budget enforcement, interrupted-state recovery, provider JSON requests, and concurrent duplicate delivery under PostgreSQL advisory locks. Crash recovery is simulated through persisted state, rather than killing a live task mid-call.

One dependency warning remains: Starlette deprecates its httpx TestClient integration in favor of httpx2. It does not prevent these checks from completing.

## Cloud container build

Initial Docker builds could not resolve the cloud proxy; after resolving its hostname using the execution environment, TLS correctly rejected the unknown proxy CA. The supported correction adds the proxy hostname mapping to the build and mounts the execution environment's existing CA bundle as a BuildKit secret. No TLS/signature/hash checks were disabled. No proxy credentials or CA files are copied into the runtime image.

From the repository root:

```bash
.venv/bin/python scripts/cloud_build.py
# Stop any host API using port 8000 before starting this deployment:
docker compose -f docker-compose.yml -f examples/compose.prebuilt.yml up --no-build -d --wait
```

For independent validation alongside the host API, an external Compose override bound the proof deployment's API to port 8001, with project name `agentflow-proof` and the prebuilt image for API, worker, and migration. Its database/queue used separate persistent volumes. The demo ran against that port before and after restarting its worker.

The optional CA mount is build-only. A live LLM behind a managed TLS-intercepting proxy may require the operator to install their organization CA into runtime trust or configure a verified CA bundle; live provider behavior was not validated here.

## Benchmark

See [benchmark-sample.json](benchmark-sample.json) for actual observations. Ten tasks, client concurrency two, Celery concurrency two, deterministic mock model, warm PostgreSQL 17 and Redis 7. Every task completed. Median submission latency: 5.46 ms. Median completion: 61.85 ms. P95 completion: 74.09 ms. Total interval: 0.3231 s. Observed completion rate: 30.95 tasks/s.

Workspace limits: 4 CPU quota, 5 visible logical CPUs, 32 GiB memory; Linux x86_64 and Python 3.12.14. The worker/API ran as local Python processes using containerized PostgreSQL and Redis. This is a tiny smoke benchmark, affected by warm caches and 50 ms polling, not a sustained load test. It excludes live inference latency, network research, cold startup, and external provider throttling. Use `examples/benchmark.py` to reproduce on your own machine; production sizing requires a longer workload and provider-specific measurements.
