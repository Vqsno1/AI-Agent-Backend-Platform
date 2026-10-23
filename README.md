# AgentFlow — AI Agent Backend Platform

A working backend MVP for queued, persistent multi-agent workflows. Built with Python 3.12+, FastAPI, PostgreSQL, SQLAlchemy, Redis, and Celery.

AgentFlow accepts a request, runs a bounded planner → research → analyst → summarizer pipeline, records each step and approved tool call, and saves results and user-scoped memory. The default mock provider demonstrates the infrastructure without credentials; it does **not** generate real research or recommendations.

```mermaid
flowchart LR
    Client -->|API key| API[FastAPI]
    API --> DB[(PostgreSQL)]
    API --> Queue[(Redis)]
    Queue --> Worker[Celery worker]
    Worker --> Pipeline[Planner → Research → Analyst → Summarizer]
    Pipeline --> Model[Mock / OpenAI-compatible model]
    Pipeline --> Tools[Approved calculator]
    Pipeline --> DB
```

## Run with Docker Compose

Prerequisites: Docker Engine and Compose v2.

```bash
cp .env.example .env
# Edit API_KEYS in .env before exposing the service.
docker compose up --build -d
curl --fail http://localhost:8000/health/ready
export API_KEY=local-development-key
# With Python dependencies installed:
uv run python examples/demo.py
```

Compose runs PostgreSQL, Redis with AOF persistence, a one-shot migration, the API, and a two-process worker. Database and Redis volumes survive `docker compose down`; `down -v` deletes their data. API binding is loopback-only by default. Swagger documentation is available at `/docs` on the running API.

## Local Python development

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/). Run these commands from the repository root:

```bash
uv sync --frozen
cp .env.example .env
# Start dependencies. Compose keeps their ports internal, so use these for host development:
docker run -d --name agentflow-postgres -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=agentflow -e POSTGRES_PASSWORD=agentflow \
  -e POSTGRES_DB=agentflow postgres:17-alpine
docker run -d --name agentflow-redis -p 127.0.0.1:6379:6379 redis:7-alpine
# Wait for pg_isready and redis-cli ping before migration/startup.
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# Separate terminal, same directory:
uv run celery -A app.workers.worker:celery worker --loglevel=info --concurrency=2
```

For restricted cloud filesystems, set `UV_CACHE_DIR=/workspace/.uv-cache` if the default cache is unwritable. Never overwrite an existing `.env` containing your settings.

## API example

```bash
curl --fail -X POST http://localhost:8000/api/v1/tasks \
  -H 'X-API-Key: local-development-key' -H 'Content-Type: application/json' \
  -d '{"prompt":"Compare FastAPI, Django, and Flask","workflow":"research_and_analysis","max_steps":6,"use_memory":true}'
# Returns HTTP 202 and task_id; then poll:
curl --fail http://localhost:8000/api/v1/tasks/TASK_ID \
  -H 'X-API-Key: local-development-key'
```

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/tasks` | Persist and enqueue work (202) |
| GET | `/api/v1/tasks?limit=20&offset=0` | Paginated tasks for your identity |
| GET | `/api/v1/tasks/{id}` | Status, result, timestamps, error category |
| POST | `/api/v1/tasks/{id}/cancel` | Cooperative cancellation |
| GET | `/api/v1/tasks/{id}/steps` | Ordered outputs and attempt counts |
| GET | `/api/v1/agents` | Available agent types |
| POST | `/api/v1/memories/search` | Body: `{"query":"Python","limit":10}` |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Database schema and Redis connectivity |

All `/api/v1` routes require `X-API-Key`. `API_KEYS` is a JSON mapping from secret keys to stable user IDs, allowing multiple identities. An absent mapping grants no access. Cross-user task access returns 404. Search always filters by authenticated identity and treats SQL wildcard characters literally.

## Live model configuration

In your ignored `.env`, set `LLM_PROVIDER=openai`, `LLM_API_KEY`, `LLM_MODEL`, and optionally `LLM_BASE_URL` for a trusted OpenAI-compatible endpoint supporting JSON mode. Restart API and worker after configuration changes. Only point the base URL at an endpoint you trust with the key and task data. No live provider credentials were available during implementation; the HTTP request contract is tested using mocked transport.

The research stage currently uses the prompt, previous memory, model knowledge, and an optional arithmetic calculator. Web search, external API tools, and document indexing are future work. Model output is schema-validated. Tool calls must pass both the registry and each agent's permissions; generated code is never executed. Tool results are recorded and passed to subsequent stages.

## Tests and validation

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q  # SQLite portability tests; PostgreSQL concurrency test skips
# Dedicated disposable PostgreSQL test database (tests erase its tables!):
docker exec agentflow-postgres createdb -U agentflow agentflow_test
TEST_DATABASE_URL=postgresql+psycopg://agentflow:agentflow@localhost:5432/agentflow_test uv run pytest -q
uv run alembic check
API_KEY=local-development-key uv run python examples/demo.py
API_KEY=local-development-key uv run python examples/benchmark.py
```

Validated in the development environment: **24 tests passed against PostgreSQL**, real Redis/Celery execution of two concurrent API tasks, and Alembic schema consistency. Tests cover ownership, memory isolation, retries, malformed model output, tool rejection/auditing, cooperative cancellation, persisted-step recovery, budget/deadline enforcement, queue errors, duplicate deliveries, and provider HTTP contracts. Recovery tests simulate interrupted state; they do not kill a live worker process. A dependency deprecation warning from Starlette's httpx TestClient remains.

A small measured run of 10 mock tasks with client concurrency 2 and worker concurrency 2 completed at 30.95 tasks/s; median POST latency was 5.46 ms, median completion 61.85 ms, and p95 completion 74.09 ms. Environment: Linux x86_64, Python 3.12.14, 4 CPU quota (5 visible logical CPUs), 32 GiB memory limit, PostgreSQL 17 and Redis 7, warm local services. This 0.323-second sample measures infrastructure with no inference latency; it is **not** a capacity claim or production benchmark. Polling interval was 50 ms. See [validation notes](docs/validation.md).

GitHub Actions runs lint/format checks, PostgreSQL tests, migrations, and an actual Redis/worker/API demo. CI has been configured; a hosted Actions run has not been observed yet.

## Reliability and boundaries

See [architecture and tradeoffs](docs/architecture.md) for status transitions, locking, retries, crash recovery, queue publication gaps, and cost reservations. This is a portfolio MVP, with no rate limiting, transactional outbox, metrics backend, semantic retrieval, streaming, dashboard, or deployment automation. Prompt boundaries and allowlisted tools limit impact but do not guarantee immunity to prompt injection. Do not deploy the development Compose credentials or example API key publicly.

## Repository layout

`app/api` schemas · `app/agents` bounded orchestration · `app/llm` provider adapter · `app/tools` tool registry · `app/services` task execution and memory · `app/db` persistence · `app/workers` Celery · `alembic` versioned migrations · `tests` behavior tests · `examples` demo and benchmark.

MIT licensed. Original project requirements are preserved in [docs/specification.md](docs/specification.md); optional roadmap features remain distinct from this implementation.
