# QA Platform — Architecture Design

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Requirement Analysis Agent (RAA)](#2-requirement-analysis-agent)
   - [Execution Sequence](#21-execution-sequence)
   - [Skills](#22-skills)
   - [Orchestration Layer](#23-orchestration-layer)
   - [Human Escalation Flow](#24-human-escalation-flow)
3. [Test Generation Agent (TGA)](#3-test-generation-agent)
   - [Execution Sequence](#31-execution-sequence)
   - [Skills](#32-skills)
4. [System Orchestration](#4-system-orchestration)
   - [Agent Communication](#41-agent-communication)
   - [Model Routing Strategy](#42-model-routing-strategy)
   - [Retry and Error Handling](#43-retry-and-error-handling)
   - [Observability](#44-observability)
5. [Output Schemas](#5-output-schemas)
   - [NormalizedRequirement](#51-normalizedrequirement)
   - [TestSuite](#52-testsuite)
6. [Practical Constraints](#6-practical-constraints)
   - [Modular vs Single-Agent](#61-modular-vs-single-agent-tradeoff)
   - [Risks and Mitigations](#62-risks-and-mitigations)
   - [Incremental Rollout](#63-incremental-rollout)
7. [Data Model](#7-data-model)
   - [State Store](#71-state-store-platform_state)
   - [Vector Store](#72-vector-store-requirements_embeddings)
   - [Local Dev Setup](#73-local-dev-setup)

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Gateway (:8001)                       │
│  POST /requirements/analyze    POST /tests/generate              │
└──────────────────────┬───────────────────────────────────────────┘
                       │
             ┌─────────▼──────────┐
             │  Temporal Workflow  │  durable execution boundary
             │   QAPipelineWorkflow│  replays from last success on crash
             └──────┬──────┬──────┘
                    │      │
       ┌────────────▼──┐ ┌─▼──────────────┐
       │  Requirement  │ │ Test Generation │
       │ Analysis Agent│─▶     Agent      │
       │    (RAA)      │ │    (TGA)        │
       └───────┬───────┘ └──────┬──────────┘
               │                │
   ┌───────────┼────────────────┼──────────────┐
   │           │                │              │
┌──▼──┐  ┌────▼──────────────┐  ┌─────▼──┐
│ LLM │  │   PostgreSQL 16+  │  │ OTel   │
│Client│  │  pgvector (RAG)  │  │  Obs.  │
└─────┘  │  platform_state   │  └────────┘
         │  (results store)  │
         └───────────────────┘
```

**Design principles:**

- Each agent represents a hard responsibility boundary — RAA produces structured requirements, TGA consumes them
- Skills are stateless functions; agents own execution order, parallelism, and state threading
- Agents do NOT call each other directly — they communicate via Temporal workflow state
- Humans remain in the loop at two explicit review gates
- Model selection is driven by task complexity, not hardcoded per skill

---

## 2. Requirement Analysis Agent

### 2.1 Execution Sequence

```
Input Artifacts (PRD / Jira / OpenAPI)
    │
    ├──── [parallel] ──────────────────────────────────────────────┐
    │   PRD Parser       Jira Parser       OpenAPI Parser           │
    │   (BALANCED)       (FAST)            (prance — no LLM)        │
    └──────────────────────────────────────────────────────────────┘
                              │
                   RequirementExtractorSkill
                   (POWERFUL — most critical step)
                              │
    ┌──── [parallel] ──────────────────────────────────────────────┐
    │  WorkflowExtractor  RuleExtractor  EntityExtractor  RAGEnricher│
    │  (BALANCED)         (BALANCED)     (BALANCED)       (pgvector) │
    └──────────────────────────────────────────────────────────────┘
                              │
                   AmbiguityDetectorSkill
                   (BALANCED)
                              │
                   ConfidenceScorerSkill
                   (pure Python — no LLM)
                              │
              ┌───────────────┴────────────────┐
         score ≥ 0.75                     score < 0.75
         no blocking ambiguities          OR blocking ambiguities
              │                                │
              │                    Human Escalation
              │                    (Temporal signal wait — up to 7 days)
              └───────────────┬────────────────┘
                              │
                   JSONGeneratorSkill
                   (Pydantic assembly + schema validation)
                              │
                   NormalizedRequirement ──→ Temporal state
```

### 2.2 Skills

---

#### PRD Parsing Skill
**File:** `agents/requirement_analysis/skills/prd_parser.py`

**Responsibility:** Normalize free-form Product Requirements Documents into structured feature/requirement data.

**Input:** Raw PRD text (markdown, plain text, or HTML)

**Output:**
```json
{
  "product_overview": "string",
  "goals": ["string"],
  "user_personas": [{"name": "string", "role": "string", "needs": ["string"]}],
  "features": [
    {
      "feature_id": "F-001",
      "title": "string",
      "description": "string",
      "acceptance_criteria": ["string"],
      "priority": "P0|P1|P2|P3"
    }
  ],
  "non_functional_requirements": ["string"],
  "constraints": ["string"],
  "assumptions": ["string"],
  "out_of_scope": ["string"]
}
```

**Why it exists:** PRDs vary wildly in structure across teams. This skill owns the normalization boundary so all downstream skills receive consistent input regardless of authoring style.

**Model tier:** BALANCED — structured extraction, not reasoning-heavy.

**Prompt strategy:** JSON-extraction with explicit schema, `temperature=0.0`, system prompt as "expert business analyst."

---

#### Jira / User Story Parsing Skill
**File:** `agents/requirement_analysis/skills/jira_parser.py`

**Responsibility:** Parse Jira JSON exports or Gherkin-style user stories into a normalized story format.

**Input:** Jira issue JSON array or user story text (Gherkin or free-form)

**Output:**
```json
{
  "stories": [
    {
      "id": "JIRA-1234",
      "title": "string",
      "description": "string",
      "given": ["string"],
      "when": ["string"],
      "then": ["string"],
      "acceptance_criteria": ["string"],
      "priority": "P1",
      "linked_issues": ["JIRA-1233"],
      "labels": ["auth", "cart"]
    }
  ]
}
```

**Why it exists:** Jira is the enterprise source of truth. This skill handles the structural variance between projects that use Gherkin vs. free-form descriptions.

**Model tier:** FAST — well-structured input, light extraction.

**Prompt strategy:** Two-pass: detect Gherkin format, then apply appropriate extraction template.

---

#### Swagger / OpenAPI Parsing Skill
**File:** `agents/requirement_analysis/skills/openapi_parser.py`

**Responsibility:** Parse OpenAPI 3.x specs into structured API contract definitions.

**Input:** OpenAPI YAML or JSON string

**Output:**
```json
{
  "api_contracts": [
    {
      "method": "POST",
      "path": "/api/v1/orders",
      "summary": "Create a new order",
      "auth_required": true,
      "request_schema": {},
      "response_schema": {"200": {}, "400": {}, "401": {}},
      "parameters": []
    }
  ]
}
```

**Why it exists:** API specs are machine-readable ground truth. `prance` resolves all `$ref` chains deterministically — no LLM is needed for parsing. LLM is used only for optional semantic annotation.

**Model tier:** None for parsing (deterministic). BALANCED for optional enrichment.

---

#### Requirement Extraction Skill ← most critical skill
**File:** `agents/requirement_analysis/skills/requirement_extractor.py`

**Responsibility:** Discretize all parsed artifacts into atomic, testable requirement units.

**Input:** Merged parsed documents (PRD features + Jira stories + API context)

**Output:**
```json
{
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "type": "FUNCTIONAL",
      "title": "User can add item to cart",
      "description": "Authenticated users can add any in-stock product to their shopping cart.",
      "acceptance_criteria": [
        "Cart item count is incremented by 1",
        "Item persists across sessions"
      ],
      "priority": "P1",
      "tags": ["cart", "checkout"],
      "source_reference": "F-003",
      "depends_on": []
    }
  ]
}
```

**Why it exists:** Everything downstream operates on these units. Quality here multiplies through the entire pipeline — poor extraction means poor tests. This is the highest-leverage skill in the platform.

**Model tier:** POWERFUL (claude-opus-4-8)

**Prompt strategy:** Chain-of-thought extraction — enumerate every distinct testable requirement, assign unique IDs, flag cross-dependencies, confirm testability. Then self-review to remove duplicates.

---

#### Workflow Extraction Skill
**File:** `agents/requirement_analysis/skills/workflow_extractor.py`

**Responsibility:** Extract user journeys and operational flows as step sequences with actors, preconditions, and postconditions.

**Input:** Requirement list

**Output:**
```json
{
  "workflows": [
    {
      "workflow_id": "WF-001",
      "name": "Add to Cart",
      "description": "string",
      "steps": [
        {
          "step_id": "S1",
          "action": "User views product detail page",
          "actor": "User",
          "preconditions": ["User is authenticated", "Product is in stock"],
          "postconditions": [],
          "alternatives": []
        },
        {
          "step_id": "S2",
          "action": "User clicks Add to Cart",
          "actor": "User",
          "preconditions": [],
          "postconditions": ["Cart item count + 1", "Item stored in cart"]
        },
        {
          "step_id": "S3",
          "action": "System returns updated cart",
          "actor": "System",
          "preconditions": [],
          "postconditions": ["Response time < 500ms"]
        }
      ],
      "happy_path": ["S1", "S2", "S3"],
      "exception_paths": [["S1", "S2-out-of-stock"], ["S1", "S2-auth-expired"]]
    }
  ]
}
```

**Why it exists:** Workflows are the skeleton of integration tests and E2E scenarios. Extracting them explicitly makes TGA generation deterministic and ensures exception paths are covered.

**Model tier:** BALANCED

---

#### Business Rule Extraction Skill
**File:** `agents/requirement_analysis/skills/rule_extractor.py`

**Responsibility:** Surface explicit AND implicit validation rules, authorization logic, computation rules, and constraints buried in requirements.

**Output:**
```json
{
  "rules": [
    {
      "rule_id": "BR-001",
      "description": "Cart quantity for a single SKU must not exceed 99",
      "rule_type": "VALIDATION",
      "applies_to": ["Cart", "REQ-001"],
      "is_explicit": false,
      "confidence": 0.72
    }
  ]
}
```

**Why it exists:** Business rules become test assertions. `is_explicit: false` rules flag potential missing acceptance criteria — surfacing them triggers a human review recommendation. Without explicit extraction, rules buried in prose never get tested.

**Prompt strategy:** "Act as a skeptical QA engineer. For each requirement, list every rule that must hold for the system to be correct. Think about validation, authorization, computations, and invariants."

---

#### Entity & Dependency Extraction Skill
**File:** `agents/requirement_analysis/skills/entity_extractor.py`

**Responsibility:** Identify domain entities, data models, and external service/system dependencies.

**Output:**
```json
{
  "entities": [
    {"name": "Cart", "type": "DATA_MODEL", "attributes": ["id", "userId", "items", "totalAmount", "updatedAt"]},
    {"name": "PaymentService", "type": "EXTERNAL_SYSTEM", "attributes": []}
  ],
  "dependencies": [
    {"dependency_id": "DEP-001", "name": "PaymentService", "type": "API", "criticality": "REQUIRED"}
  ]
}
```

**Why it exists:** Entities become test data factories. Dependencies become mock/stub targets. Explicit dependency mapping prevents the TGA from generating tests that assume services are always available.

---

#### Ambiguity Detection Skill
**File:** `agents/requirement_analysis/skills/ambiguity_detector.py`

**Responsibility:** Flag requirements that are vague, contradictory, incomplete, or contain implicit assumptions that could cause test cases to be untestable or wrong.

**Output:**
```json
{
  "ambiguities": [
    {
      "ambiguity_id": "AMB-001",
      "description": "REQ-003 states 'response should be fast' without defining a latency threshold",
      "severity": "HIGH",
      "affected_requirement": "REQ-003",
      "suggested_clarification": "Define the acceptable p95 response time (e.g., < 200ms under normal load)",
      "blocking": false
    }
  ]
}
```

**Severity guide:**
- `BLOCKING` — cannot generate valid tests without resolution; forces human escalation
- `HIGH` — likely generates incorrect or misleading tests
- `MEDIUM` — generates incomplete tests; assumptions noted
- `LOW` — minor; tests can proceed with stated assumptions

**Prompt strategy:** Per-requirement checklist: (1) Is expected behavior measurable? (2) Unstated assumptions? (3) Contradictions with other requirements? (4) Unaddressed edge cases or error conditions?

---

#### RAG Context Enrichment Skill
**File:** `agents/requirement_analysis/skills/rag_enricher.py`

**Responsibility:** Retrieve semantically similar historical requirements and their associated test outcomes from the PostgreSQL + pgvector store.

**Retrieval strategy:**
1. Embed each requirement title+description using `all-MiniLM-L6-v2` (384 dimensions)
2. Cosine similarity search via pgvector `<=>` operator (cosine distance)
3. `score_threshold=0.7`, top-5 results per requirement
4. Optional tag-based pre-filter for domain scoping (`tags @> $tags`)

**Output:**
```json
{
  "similar_requirements": [
    {
      "requirement_id": "REQ-OLD-047",
      "similarity": 0.92,
      "test_outcome": "Failed: cart concurrency race condition on simultaneous add"
    }
  ],
  "relevant_domain_knowledge": ["Payment flows require idempotency keys"],
  "historical_test_patterns": ["Verify cart state under concurrent updates"]
}
```

**Why it exists:** Prevents rediscovering known failure modes. Reuses institutional knowledge across teams. Particularly valuable for concurrency patterns, security edge cases, and compliance requirements that are easy to overlook.

---

#### Requirement Confidence Scoring Skill
**File:** `agents/requirement_analysis/skills/confidence_scorer.py`

**Responsibility:** Compute a holistic confidence score (0.0–1.0) for the requirement analysis output. This score drives the human escalation decision.

**Scoring formula:**
```
source_completeness  = parseable_fields / expected_fields           (weight: 0.25)
entity_coverage      = entities_found / reqs_referencing_entities   (weight: 0.25)
rule_coverage        = rules_found / (acceptance_criteria / 2)      (weight: 0.30)
ambiguity_penalty    = 1.0 - (high_severity × 0.1 + blocking × 0.3)(weight: 0.20)

confidence = sum(component × weight)
```

**Escalation triggers:**
- `confidence < MIN_CONFIDENCE_FOR_AUTO_PROCEED` (default: 0.75)
- Any `blocking` ambiguities
- High-severity ambiguity count > `MAX_AMBIGUITIES_FOR_AUTO_PROCEED` (default: 3)

**Model tier:** None — pure Python calculation, no LLM needed.

---

#### JSON Generator Skill
**File:** `agents/requirement_analysis/skills/json_generator.py`

**Responsibility:** Assemble all extraction outputs into the canonical `NormalizedRequirement` Pydantic model with full schema validation.

**Why it exists:** Centralizes schema enforcement. All upstream skills return raw dicts; this skill owns the final type-safe assembly. If Pydantic validation fails here, the agent returns a `FAILED` status rather than propagating malformed data to the TGA.

### 2.3 Orchestration Layer

```python
# agent.py — execution order

# Step 1: Parse artifacts in parallel (only parsers that have input)
[PRDParser, JiraParser, OpenAPIParser]  → parallel asyncio.gather

# Step 2: Extract discrete requirements (sequential — depends on step 1)
RequirementExtractor(merged_parsed)     → requirements[]

# Step 3: Parallel extraction + RAG enrichment (all depend on step 2)
[WorkflowExtractor, RuleExtractor, EntityExtractor, RAGEnricher] → parallel asyncio.gather

# Step 4: Ambiguity detection (depends on step 3)
AmbiguityDetector(requirements, rules)  → ambiguities[]

# Step 5: Confidence scoring (depends on steps 3–4)
ConfidenceScorer(requirements, workflows, rules, entities, ambiguities) → float

# Step 6: Escalation check
if confidence < threshold OR blocking_ambiguities > 0 OR high_ambiguities > limit:
    status = AWAITING_REVIEW
    human_review_required = True

# Step 7: Schema assembly (always)
JSONGenerator(all outputs + metadata)   → NormalizedRequirement
```

**State handling:** Skills are pure functions — no shared state between them. The agent passes outputs explicitly from one stage to the next. This makes the pipeline trivially testable via mocks and avoids hidden coupling.

**Retry handling:** Implemented at the `LLMClient` level via `tenacity` (3 retries, exponential backoff). If all retries exhaust, the exception propagates to the Temporal activity, which applies its own retry policy.

**Schema enforcement:** Pydantic v2 validates all skill outputs at assembly time. `ValidationError` from any field causes a `FAILED` status — partial outputs are never propagated downstream.

### 2.4 Human Escalation Flow

```
Workflow pauses at AWAITING_REVIEW
    │
    ├── Notification sent (webhook/email — integration point TBD)
    │
    ├── Human reviews NormalizedRequirement via UI or API:
    │     GET /api/v1/requirements/{id}
    │
    ├── Human approves:
    │     POST /api/v1/requirements/{id}/review {"approved": true}
    │     → status = APPROVED, workflow signal received, pipeline continues to TGA
    │
    └── Human rejects with feedback:
          POST /api/v1/requirements/{id}/review {"approved": false, "reason": "..."}
          → status = REJECTED, workflow ends, feedback stored for re-run
```

---

## 3. Test Generation Agent

### 3.1 Execution Sequence

```
NormalizedRequirement (from RAA)
    │
    ├──── [parallel by domain] ─────────────────────────────────────┐
    │  FunctionalGenerator  APITestGenerator  SecurityGenerator      │
    │  (→ PositiveScenario  (per endpoint)    MobileUIGenerator      │
    │     NegativeScenario                                           │
    │     EdgeCaseGenerator)                                         │
    └───────────────────────────────────────────────────────────────┘
                              │
                   AssertionGeneratorSkill
                   (FAST — converts prose expectations to typed assertions)
                              │
                   DeduplicatorSkill
                   (embedding-based — no LLM)
                              │
                   RiskPriorizerSkill
                   (rule-based — no LLM)
                              │
                   TestFormatterSkill
                   (Pydantic validation + schema normalization)
                              │
                   ScaffoldGeneratorSkill
                   (BALANCED — P0/P1 non-duplicates only)
                              │
                   TestSuite → Human Review Gate
```

### 3.2 Skills

---

#### Functional Generator Skill
**File:** `agents/test_generation/skills/functional_generator.py`

**Responsibility:** Coordinator skill. Iterates over all `FUNCTIONAL` requirements and invokes Positive, Negative, and Edge Case skills for each. Runs all three sub-skills per requirement in parallel.

**Why it exists:** Separating scenario types ensures each category gets dedicated generation logic. Without a coordinator, generators tend to produce only happy-path tests.

---

#### Positive Scenario Skill
**File:** `agents/test_generation/skills/positive_scenario.py`

**Responsibility:** Generate valid-input, expected-success test cases.

**Model tier:** BALANCED

**Prompt strategy:**
> "Given this requirement and business rules, generate 2–4 positive test cases that verify correct system behavior when all preconditions are met and inputs are valid. Include preconditions, steps, expected results, and test data."

---

#### Negative Scenario Skill
**File:** `agents/test_generation/skills/negative_scenario.py`

**Responsibility:** Generate test cases for invalid inputs, unauthorized access, state violations, missing required fields.

**Coverage categories:**
- Missing required fields
- Invalid data types or formats
- Out-of-range values
- Unauthorized access attempts
- State violations (wrong preconditions)

**Model tier:** BALANCED

---

#### Edge Case Generator Skill
**File:** `agents/test_generation/skills/edge_case_generator.py`

**Responsibility:** Generate boundary and unusual-but-valid test cases.

**Model tier:** POWERFUL — edge cases require deeper reasoning about system behavior under unusual conditions.

**Coverage categories explicitly prompted:**
- Boundary values (min, max, min±1, max±1)
- Concurrent/parallel operations on the same resource
- Timezone, locale, and character encoding variations
- Pagination boundaries and empty result sets
- Retry same operation twice (idempotency check)
- Long-running operations and timeout conditions

---

#### API Test Generator Skill
**File:** `agents/test_generation/skills/api_test_generator.py`

**Responsibility:** Generate test cases from `api_contracts` in the NormalizedRequirement.

**Per endpoint, generates:**
1. Happy path (valid request, expected 2xx response)
2. All documented error codes (400, 401, 403, 404, 422, 500)
3. Auth/authz tests (missing token, expired token, insufficient permissions)
4. Schema validation tests (malformed request body, missing required fields)

**Model tier:** BALANCED. One LLM call per endpoint, run in parallel via `asyncio.gather`.

---

#### Security-Oriented Test Generator Skill
**File:** `agents/test_generation/skills/security_test_generator.py`

**Responsibility:** Generate test cases to VERIFY that security defenses are correctly implemented.

**Important:** This skill generates *defensive test assertions* — not exploit code. Each test case asserts that a security control works (e.g., "verify 401 is returned when JWT is expired"). No attack payloads are generated.

**OWASP Top 10 controls covered:**
- Authentication and session management
- Authorization / object-level access control (IDOR)
- Input validation (verify rejection of malformed inputs)
- Sensitive data exposure
- Rate limiting / brute force protection
- Broken access control

**Model tier:** BALANCED

---

#### Mobile / UI Test Generator Skill
**File:** `agents/test_generation/skills/mobile_ui_generator.py`

**Responsibility:** Generate UI test cases from workflow graphs. Maps workflow steps to page interactions. Generates Page Object Model stubs for each identified UI entity.

**Framework selection:**
- Web UI → Playwright (async Python)
- Mobile → Appium (Python client)

Only triggered when requirements are tagged `ui`, `mobile`, or `frontend`, or when workflows are available.

**Model tier:** BALANCED

---

#### Assertion Generator Skill
**File:** `agents/test_generation/skills/assertion_generator.py`

**Responsibility:** Post-process all test cases and enrich them with typed, automation-ready assertion objects.

**Conversion example:**
- Human-readable: "verify the response contains the order ID"
- Typed assertion: `{"assertion_type": "RESPONSE_BODY", "path": "$.order_id", "operator": "IS_NOT_NULL"}`

**Why it exists:** Test case generators produce human-readable expected results. This skill converts them to structured `Assertion` objects that automation frameworks can execute directly.

**Model tier:** FAST — pattern-matching conversion, not deep reasoning.

**Batching:** Processes cases in batches of 20 to stay within token limits.

---

#### Test Deduplication Skill
**File:** `agents/test_generation/skills/deduplicator.py`

**Responsibility:** Identify semantically duplicate test cases generated by parallel skill execution.

**Algorithm:**
1. Embed each test case title+description using `all-MiniLM-L6-v2`
2. Compute pairwise cosine similarity matrix
3. Pairs with similarity ≥ 0.92 → flag the weaker one as duplicate
4. "Weaker" = fewer assertions + steps (less coverage)
5. Marked duplicates remain in the TestSuite with `is_duplicate: true` for traceability

**Why it exists:** Parallel domain generators inevitably produce overlapping cases. Deduplication prevents inflated test suites and reviewer fatigue. No LLM needed — pure embedding similarity.

---

#### Risk-Based Prioritization Skill
**File:** `agents/test_generation/skills/risk_prioritizer.py`

**Responsibility:** Assign P0–P3 priority to each test case based on type, tags, and content signals.

**Priority assignment rules:**
| Priority | Conditions |
|----------|-----------|
| P0 | Type=SECURITY, or tags include `security`, `payment`, `auth`, `authorization`, `data-loss` |
| P1 | Positive functional tests for core journeys; API write operations (POST/PUT/DELETE) |
| P2 | Negative scenarios, read API operations, non-critical edge cases |
| P3 | Nice-to-have coverage, cosmetic assertions |

**Model tier:** None — rule-based. LLM not used.

---

#### Test Formatter Skill
**File:** `agents/test_generation/skills/test_formatter.py`

**Responsibility:** Normalize all test cases to the canonical `TestCase` Pydantic schema. Cases that fail validation are logged and skipped rather than crashing the pipeline.

---

#### Automation Scaffold Generator Skill
**File:** `agents/test_generation/skills/scaffold_generator.py`

**Responsibility:** Generate runnable pytest/Playwright/Appium scaffolds for P0 and P1 non-duplicate test cases.

**Why only P0/P1:** Generating scaffolds for all cases is expensive. P2/P3 cases are generated as structured test data that engineers can scaffold manually when needed.

**Example Playwright output:**
```python
async def test_tc001_authenticated_user_adds_item_to_cart(page: Page) -> None:
    # Preconditions: user authenticated, SKU-001 in stock, cart empty
    await page.goto("/products/SKU-001")
    await page.click("[data-testid=add-to-cart-btn]")
    await expect(page.locator("[data-testid=cart-count]")).to_have_text("1")
```

**Example pytest API scaffold:**
```python
async def test_tc015_post_order_returns_201(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/orders",
        json={"sku": "SKU-001", "quantity": 1},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 201
    assert response.json()["order_id"] is not None
```

**Model tier:** BALANCED

---

## 4. System Orchestration

### 4.1 Agent Communication

Agents communicate via **Temporal workflow state** — not direct calls.

```
HTTP POST /requirements/analyze
    ↓
FastAPI creates Temporal workflow execution (workflow_id = requirement reference)
    ↓
Temporal Activity Set 1: run_raa_activity
    → NormalizedRequirement serialized as activity output
    → Stored in state via store_normalized_requirement_activity
    ↓
[Optional] Temporal waits for approve_raa signal (up to 7 days)
    ↓
Temporal Activity Set 2: run_tga_activity
    → TestSuite serialized as activity output
    → Stored in state via store_test_suite_activity
    ↓
Temporal waits for approve_tga signal
    ↓
Workflow completes with final status
```

**Why Temporal:** If the process crashes mid-pipeline, Temporal replays from the last successful activity. For a 10–20 minute LLM pipeline, durable execution is non-negotiable. The alternative (stateless HTTP + database polling) adds operational complexity without the replay guarantee.

**Running without Temporal (dev/test):** The API routes call agents directly and store results in Postgres via `StateStore`. State survives restarts. If Postgres is also unavailable, `InMemoryStateStore` is used as a last-resort fallback — results are lost on restart.

### 4.2 Model Routing Strategy

Centralized in `orchestration/router.py`. Skills declare their tier; the `LLMClient` resolves the model name.

| Skill | Tier | Rationale |
|-------|------|-----------|
| RequirementExtractorSkill | POWERFUL | Highest-stakes — quality here multiplies downstream |
| EdgeCaseGeneratorSkill | POWERFUL | Requires deep reasoning about failure modes |
| PRDParserSkill | BALANCED | Structured extraction |
| WorkflowExtractorSkill | BALANCED | Pattern-matching over requirements |
| RuleExtractorSkill | BALANCED | Medium reasoning depth |
| EntityExtractorSkill | BALANCED | Medium reasoning depth |
| AmbiguityDetectorSkill | BALANCED | Requires judgment but not max reasoning |
| PositiveScenarioSkill | BALANCED | Standard generation |
| NegativeScenarioSkill | BALANCED | Standard generation |
| APITestGeneratorSkill | BALANCED | Spec-driven generation |
| SecurityTestGeneratorSkill | BALANCED | Medium reasoning |
| MobileUIGeneratorSkill | BALANCED | Pattern-based mapping |
| ScaffoldGeneratorSkill | BALANCED | Code generation — needs syntax reliability |
| JiraParserSkill | FAST | Well-structured input |
| AssertionGeneratorSkill | FAST | Pattern-matching conversion |
| RiskPriorizerSkill | FAST | Rule-based |
| ConfidenceScorerSkill | None | Pure Python |
| DeduplicatorSkill | None | Embedding similarity |
| OpenAPIParserSkill | None | Deterministic parsing via prance |

**Override:** Modify `orchestration/router.py` to change tier per skill without touching skill code.

### 4.3 Retry and Error Handling

```
LLM API timeout / rate limit
    → tenacity retry (3 attempts, exponential backoff, max 10s delay)
    → if all exhausted: exception propagates to Temporal activity
    → Temporal applies its own retry policy (3 attempts, 2s initial, 2x backoff)

LLM returns invalid JSON
    → LLMClient strips markdown fences and retries json.loads
    → if still invalid: ValidationError raised, skill returns failure

Qdrant unavailable
    → RAGEnricherSkill catches connection error
    → Returns empty EnrichedContext, logs warning
    → Pipeline continues with reduced confidence score

Pydantic ValidationError in JSONGeneratorSkill or TestFormatterSkill
    → FAILED status returned (RAA) or case skipped (TGA)
    → No partial/malformed data propagated downstream

All Temporal activity retries exhausted
    → Workflow fails with structured error
    → State preserved — operator can inspect and retry manually
```

### 4.4 Observability

All skill executions emit structured log events via `structlog`:
```python
logger.info("prd_parser.complete", feature_count=12, duration_ms=834)
logger.info("raa.process.complete", confidence=0.87, human_review_required=False, duration_ms=18420)
```

OpenTelemetry spans wrap each agent execution (FastAPI auto-instrumentation via `opentelemetry-instrumentation-fastapi`). Span attributes include: model, skill name, input/output token counts, confidence score, escalation decision.

**Key metrics to track:**
- RAA confidence score distribution per team
- Escalation rate (% of runs requiring human review)
- TGA test case count by type and priority
- Deduplication rate (indicates prompt overlap between generators)
- Scaffold generation success rate

---

## 5. Output Schemas

### 5.1 NormalizedRequirement

The canonical output contract of the RAA. The TGA has a hard dependency on this schema — changes here require versioning.

**Full schema** (defined in `schemas/requirements.py`):

```json
{
  "requirement_id": "NR-A3F2B1C9",
  "source": {
    "type": "PRD",
    "reference": "checkout-v2-prd-2026-01",
    "url": "https://confluence.example.com/...",
    "raw_content_hash": "sha256:abc123"
  },
  "metadata": {
    "created_at": "2026-06-05T10:30:00Z",
    "version": "1.0",
    "confidence_score": 0.82,
    "processing_model": "balanced",
    "skills_executed": [
      "PRDParserSkill",
      "RequirementExtractorSkill",
      "WorkflowExtractorSkill",
      "RuleExtractorSkill",
      "EntityExtractorSkill",
      "RAGEnricherSkill",
      "AmbiguityDetectorSkill",
      "ConfidenceScorerSkill",
      "JSONGeneratorSkill"
    ],
    "processing_duration_ms": 18420
  },
  "status": "APPROVED",
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "type": "FUNCTIONAL",
      "title": "User can add item to cart",
      "description": "Authenticated users can add any in-stock product to their shopping cart. The cart persists across sessions.",
      "acceptance_criteria": [
        "Cart item count is incremented by 1",
        "Item appears in cart with correct price and quantity",
        "Cart persists if user navigates away and returns"
      ],
      "priority": "P1",
      "tags": ["cart", "checkout"],
      "source_reference": "F-003"
    }
  ],
  "entities": [
    {
      "name": "Cart",
      "type": "DATA_MODEL",
      "attributes": ["id", "userId", "items", "totalAmount", "updatedAt"]
    },
    {
      "name": "Product",
      "type": "DATA_MODEL",
      "attributes": ["id", "name", "price", "stockCount", "sku"]
    }
  ],
  "workflows": [
    {
      "workflow_id": "WF-001",
      "name": "Add to Cart",
      "description": "User adds an in-stock product to their cart",
      "steps": [
        {
          "step_id": "S1",
          "action": "User views product detail page",
          "actor": "User",
          "preconditions": ["User is authenticated", "Product SKU-001 is in stock"],
          "postconditions": [],
          "alternatives": []
        },
        {
          "step_id": "S2",
          "action": "User clicks Add to Cart",
          "actor": "User",
          "preconditions": [],
          "postconditions": ["Cart item count + 1", "Item stored in cart"]
        },
        {
          "step_id": "S3",
          "action": "System returns updated cart",
          "actor": "System",
          "preconditions": [],
          "postconditions": ["Response time < 500ms"]
        }
      ],
      "happy_path": ["S1", "S2", "S3"],
      "exception_paths": [
        ["S1", "S2-out-of-stock"],
        ["S1", "S2-auth-expired"]
      ]
    }
  ],
  "business_rules": [
    {
      "rule_id": "BR-001",
      "description": "Cart quantity for a single SKU must not exceed 99",
      "rule_type": "VALIDATION",
      "applies_to": ["Cart"],
      "is_explicit": false,
      "confidence": 0.72
    }
  ],
  "dependencies": [
    {
      "dependency_id": "DEP-001",
      "name": "InventoryService",
      "type": "API",
      "criticality": "REQUIRED"
    }
  ],
  "api_contracts": [],
  "ambiguities": [],
  "enriched_context": {
    "similar_requirements": [],
    "relevant_domain_knowledge": [],
    "historical_test_patterns": []
  },
  "human_review_required": false,
  "review_reasons": []
}
```

### 5.2 TestSuite

The canonical output contract of the TGA.

```json
{
  "test_suite_id": "TS-B7E3D2A1",
  "source_requirement_id": "NR-A3F2B1C9",
  "metadata": {
    "generated_at": "2026-06-05T10:32:15Z",
    "generation_model": "balanced",
    "total_test_cases": 24,
    "by_type": {"FUNCTIONAL": 12, "API": 6, "SECURITY": 3, "EDGE_CASE": 3},
    "by_priority": {"P0": 2, "P1": 8, "P2": 10, "P3": 4},
    "coverage_estimate": 0.85,
    "human_review_required": true,
    "review_reasons": ["First generation for this feature — human review recommended"]
  },
  "test_cases": [
    {
      "test_id": "TC-001A2B3C",
      "source_requirement_id": "REQ-001",
      "type": "FUNCTIONAL",
      "priority": "P1",
      "title": "Authenticated user adds in-stock item to empty cart",
      "description": "Verify that an authenticated user can add a single in-stock product to an empty cart",
      "preconditions": [
        "User is authenticated",
        "Product SKU-001 is in stock (qty: 10)",
        "User cart is empty"
      ],
      "steps": [
        {
          "step_number": 1,
          "action": "Navigate to /products/SKU-001",
          "expected_result": "Product detail page loads with Add to Cart button enabled",
          "test_data": null
        },
        {
          "step_number": 2,
          "action": "Click Add to Cart button",
          "expected_result": "Cart icon shows count 1",
          "test_data": {"sku": "SKU-001", "quantity": 1}
        }
      ],
      "expected_results": [
        "Cart contains 1 item",
        "Cart total equals product price",
        "Response time < 500ms"
      ],
      "assertions": [
        {
          "assertion_id": "ASSERT-001",
          "description": "Cart item count is 1",
          "assertion_type": "UI_ELEMENT",
          "expected_value": "1",
          "operator": "EQUALS"
        },
        {
          "assertion_id": "ASSERT-002",
          "description": "API returns HTTP 200",
          "assertion_type": "STATUS_CODE",
          "expected_value": 200,
          "operator": "EQUALS"
        },
        {
          "assertion_id": "ASSERT-003",
          "description": "Response time under 500ms",
          "assertion_type": "RESPONSE_TIME_MS",
          "expected_value": 500,
          "operator": "LESS_THAN"
        }
      ],
      "test_data": {},
      "tags": ["functional", "cart", "positive"],
      "automation_scaffold": {
        "framework": "PLAYWRIGHT",
        "language": "python",
        "scaffold_code": "async def test_tc001_authenticated_user_adds_item(page: Page) -> None:\n    await page.goto('/products/SKU-001')\n    await page.click('[data-testid=add-to-cart-btn]')\n    await expect(page.locator('[data-testid=cart-count]')).to_have_text('1')",
        "file_path_suggestion": "tests/e2e/cart/test_add_to_cart.py",
        "imports": ["from playwright.async_api import Page, expect"],
        "fixtures_required": ["authenticated_page", "empty_cart", "in_stock_sku_001"]
      },
      "risk_score": 0.75,
      "is_duplicate": false,
      "duplicate_of": null
    }
  ]
}
```

---

## 6. Practical Constraints

### 6.1 Modular vs Single-Agent Tradeoff

**Use this modular orchestration design when:**
- Multiple input types exist simultaneously (PRD + Jira + OpenAPI)
- Different model tiers are appropriate for different tasks
- Skills need independent retry policies and deployment cycles
- Multiple engineers/teams contribute to the platform
- The system needs to scale across teams with different requirements

**Use single-agent architecture when:**
- Single input type (Jira stories only, for example)
- Team size < 3 engineers
- Proof-of-concept or MVP phase
- A single Claude tool-use API call with a well-structured prompt handles the task adequately

**The boundary:** Single-agent architectures are simpler below ~5 distinct reasoning tasks. Above that, the context window becomes a liability (all intermediate state competes for tokens), retry logic tangles (you can't retry just the broken step), and you lose independent deployability of skill improvements.

**When NOT to use this architecture:**
- The overhead of Temporal/Qdrant/multiple LLM calls is not justified by volume
- Requirements are highly structured and consistent (e.g., auto-generated from a fixed template) — a deterministic parser may suffice

### 6.2 Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM hallucination in requirement extraction | Wrong tests, false confidence | Confidence gate (0.75) + human review; ambiguity detection catches most hallucinated requirements |
| Test case explosion (too many generated cases) | Reviewer fatigue | Deduplication skill + risk-based prioritization — only P0/P1 get scaffolds |
| Stale RAG context from outdated requirements | Historical patterns mislead current analysis | Periodic DELETE on `requirements_embeddings` rows older than 6 months; `score_threshold=0.7` prevents weak matches |
| Temporal workflow gets stuck in signal wait | Pipeline blocked indefinitely | 7-day timeout on human review signals; fallback alert to oncall |
| Cost overrun from POWERFUL tier | Budget impact | Model routing — only 2 skills use opus (RequirementExtractor, EdgeCaseGenerator) |
| High confidence score, wrong output | Missed review gate | Human review always ON for first N runs per team; review rate configurable |
| Broken schema between RAA and TGA | Runtime failures | Pydantic v2 validates at assembly time; FAILED status prevents propagation |
| LLM output contains non-JSON prose | Parsing failure | LLMClient strips markdown fences; single retry on parse failure before raising |

---

## 7. Data Model

Both agents share a single PostgreSQL 16+ instance. The database has two purposes:
1. **State persistence** — durable storage for pipeline results (`platform_state`)
2. **RAG vector search** — embedding-based requirement retrieval (`requirements_embeddings`)

### 7.1 State Store (`platform_state`)

A generic JSONB key-value table. All pipeline outputs are serialized as JSON and stored here, keyed by a namespaced prefix.

```sql
CREATE TABLE platform_state (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fast lookup by type (all requirements, all test suites)
CREATE INDEX platform_state_type_idx
    ON platform_state (split_part(key, ':', 1));
```

**Key namespaces:**

| Prefix | Example key | Stores |
|--------|-------------|--------|
| `normalized_requirement:` | `normalized_requirement:NR-A3F2B1` | `NormalizedRequirement` JSON |
| `test_suite:` | `test_suite:TS-B7E3D2` | `TestSuite` JSON |

**Key design decisions:**
- JSONB over typed columns — the RAA/TGA schemas evolve independently; no migrations needed for field additions
- Single table — keeps infrastructure minimal; separate tables add no query benefit since all access is by primary key
- `updated_at` tracks review mutations (approve/reject changes the `status` field in-place via upsert)

**Graceful degradation:** If Postgres is unavailable at startup, the application falls back to `InMemoryStateStore`. The pipeline runs normally; results are lost on restart. A startup log line indicates which backend is active:
```
state_store.using_postgres  (normal)
state_store.postgres_unavailable error=... detail=Results will not persist across restarts  (fallback)
```

### 7.2 Vector Store (`requirements_embeddings`)

Stores embeddings of historical requirements for RAG context enrichment.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE requirements_embeddings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id TEXT UNIQUE NOT NULL,   -- REQ-001, etc.
    tags           TEXT[],                 -- domain scope filter
    payload        JSONB NOT NULL,         -- full requirement metadata
    embedding      VECTOR(384)             -- all-MiniLM-L6-v2 output
);

-- ivfflat index for approximate nearest-neighbour search
CREATE INDEX requirements_embeddings_embedding_idx
    ON requirements_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**Similarity query used by RAGEnricherSkill:**
```sql
SELECT payload, 1 - (embedding <=> $1::vector) AS score
FROM requirements_embeddings
WHERE 1 - (embedding <=> $1::vector) >= 0.7   -- score_threshold
ORDER BY score DESC
LIMIT 5;
```

`<=>` is pgvector's cosine distance operator. `1 - distance = similarity`.

### 7.3 Local Dev Setup

One Docker command starts everything needed:

```bash
docker run -d --name qa-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=qa_platform \
  -p 5432:5432 \
  pgvector/pgvector:pg17
```

The application creates all tables and indexes automatically on startup — no manual migration step.

**Default `DATABASE_URL`:** `postgresql://postgres:postgres@localhost:5432/qa_platform`

Override in `.env`:
```
DATABASE_URL=postgresql://user:pass@host:5432/qa_platform
```

### 6.3 Incremental Rollout

The platform is designed for incremental adoption — teams do not need to adopt everything at once.

| Phase | Scope | Success Metric |
|-------|-------|---------------|
| 1 (weeks 1–4) | RAA only; all output to human review | Extraction quality > 80% acceptance rate by reviewers |
| 2 (weeks 5–8) | Add TGA for API tests only | API test coverage increase vs. manual baseline |
| 3 (weeks 9–12) | Full pipeline — functional + edge case tests | Reduction in manual test writing time (target: 40%) |
| 4 (weeks 13+) | Lower human review threshold per team | Confidence calibration shows < 5% bad test rate at 0.75 threshold |

**Governance:** Each team's confidence threshold and review requirements are configurable independently. A team processing well-structured Jira stories can lower their threshold sooner than a team whose primary input is unstructured PRD documents.
