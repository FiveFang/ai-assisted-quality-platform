# AI-assisted QA Platform

AI-assisted QA platform that consumes requirement artifacts (PRDs, Jira stories, OpenAPI specs) and generates structured, automation-ready test scenarios — keeping humans in the review and approval loop.

## Overview

Two AI agents work in sequence:

1. **Requirement Analysis Agent (RAA)** — parses inputs, extracts requirements, workflows, business rules, and entities; enriches via RAG; scores confidence; outputs a validated `NormalizedRequirement` JSON
2. **Test Generation Agent (TGA)** — consumes `NormalizedRequirement` and generates functional, API, security, and UI test cases with Playwright/pytest scaffolds; deduplicates and risk-prioritizes output; produces a `TestSuite`

Human review gates sit between and after each agent. Low confidence or blocking ambiguities force escalation before test generation begins.

---

## Requirements

- Python 3.11+
- [Qdrant](https://qdrant.tech/) (local Docker or hosted) — vector store for RAG
- [Temporal](https://temporal.io/) (optional for dev) — durable workflow orchestration
- Anthropic API key

---

## Setup

### 1. Clone and install

```bash
git clone <repo>
cd qa-platform
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY at minimum
```

Minimum required:
```
ANTHROPIC_API_KEY=sk-ant-...
```

Everything else has sensible defaults for local development.

### 3. Start Qdrant (Docker)

```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

### 4. Start Temporal (optional — skip for dev/test)

```bash
# Via Temporal CLI
temporal server start-dev
```

If Temporal is not running, the platform uses the in-memory state store (not durable — dev only).

### 5. Run the API server

```bash
uvicorn qa_platform.api.main:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=qa_platform --cov-report=term-missing
```

Type checking:
```bash
mypy src/
```

Linting:
```bash
ruff check src/ tests/
```

---

## Usage

### 1. Analyze requirements

```bash
curl -X POST http://localhost:8000/api/v1/requirements/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "PRD",
    "reference": "checkout-v2-prd",
    "raw_inputs": {
      "prd": "Feature: Shopping Cart\n\nUsers can add items to cart.\nAcceptance criteria:\n- Cart count increments\n- Items persist across sessions"
    }
  }'
```

Response: `NormalizedRequirement` JSON with `requirement_id`, confidence score, extracted requirements, workflows, business rules.

### 2. Review RAA output (if `human_review_required: true`)

```bash
curl -X POST http://localhost:8000/api/v1/requirements/{requirement_id}/review \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### 3. Generate tests

```bash
curl -X POST http://localhost:8000/api/v1/tests/generate \
  -H "Content-Type: application/json" \
  -d '{"requirement_id": "{requirement_id}"}'
```

Response: `TestSuite` JSON with test cases, assertions, and Playwright/pytest scaffolds for P0/P1 cases.

### 4. Review TGA output

```bash
curl -X POST http://localhost:8000/api/v1/tests/{test_suite_id}/review \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/requirements/analyze` | Submit artifacts for RAA processing |
| `GET`  | `/api/v1/requirements/{id}` | Retrieve a `NormalizedRequirement` |
| `POST` | `/api/v1/requirements/{id}/review` | Approve or reject RAA output |
| `POST` | `/api/v1/tests/generate` | Run TGA on an approved requirement |
| `GET`  | `/api/v1/tests/{id}` | Retrieve a `TestSuite` |
| `POST` | `/api/v1/tests/{id}/review` | Approve or reject TGA output |
| `GET`  | `/health` | Health check |

---

## Project Structure

```
src/qa_platform/
├── config.py                        # Settings (pydantic-settings), ModelTier, MODEL_MAP
├── schemas/
│   ├── common.py                    # Shared enums and ID generation
│   ├── requirements.py              # NormalizedRequirement — RAA output contract
│   └── test_cases.py                # TestSuite, TestCase — TGA output contract
├── infrastructure/
│   ├── llm_client.py                # Anthropic client with model routing and retry
│   ├── vector_store.py              # Qdrant wrapper for RAG
│   └── state_store.py               # In-memory state store (dev fallback)
├── agents/
│   ├── requirement_analysis/
│   │   ├── agent.py                 # RAA orchestrator
│   │   └── skills/                  # 11 independent skills
│   └── test_generation/
│       ├── agent.py                 # TGA orchestrator
│       └── skills/                  # 12 independent skills
├── orchestration/
│   ├── workflow.py                  # Temporal QAPipelineWorkflow
│   ├── activities.py                # Temporal activity definitions
│   └── router.py                    # Skill → ModelTier routing table
└── api/
    ├── main.py                      # FastAPI application
    └── routes/
        ├── requirements.py
        └── tests.py
```

---

## Model Tiers

| Tier | Model | Used For |
|------|-------|----------|
| `fast` | `claude-haiku-4-5-20251001` | Jira parsing, assertion enrichment, risk prioritization |
| `balanced` | `claude-sonnet-4-6` | Most skills — PRD parsing, workflow/rule/entity extraction, scenario generation |
| `powerful` | `claude-opus-4-8` | Requirement extraction (most critical), edge case generation |

Override the default tier in `.env`:
```
DEFAULT_MODEL_TIER=balanced
```

Override the routing table per-skill in [src/qa_platform/orchestration/router.py](src/qa_platform/orchestration/router.py).

---

## Human Review Gates

The platform is intentionally not fully autonomous. Two review gates exist:

1. **After RAA** — triggered automatically when:
   - Confidence score < `MIN_CONFIDENCE_FOR_AUTO_PROCEED` (default: 0.75)
   - Any blocking ambiguities detected
   - High-severity ambiguity count > `MAX_AMBIGUITIES_FOR_AUTO_PROCEED` (default: 3)

2. **After TGA** — always enabled for first-run teams; configurable per team

When using Temporal, the workflow pauses at each gate and waits for an HTTP signal (approve/reject). When running without Temporal, the state store records the decision and the next API call checks it.

---

## Incremental Rollout

| Phase | Scope | Goal |
|-------|-------|------|
| 1 (wk 1–4) | RAA only, all output to human review | Calibrate extraction quality |
| 2 (wk 5–8) | TGA for API tests only | Most deterministic — spec-driven |
| 3 (wk 9–12) | Full pipeline — functional + edge cases | End-to-end coverage |
| 4 (wk 13+) | Reduce human review threshold | As confidence calibrates per team |

---

## Design

See [DESIGN.md](DESIGN.md) for the full architecture, skill design, orchestration patterns, schema definitions, example JSON outputs, and tradeoff analysis.
