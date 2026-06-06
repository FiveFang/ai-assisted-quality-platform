# QA Platform — UI/UX Design

## Design Philosophy

The platform has two types of users and one critical interaction:

- **Analysts / PMs** — submit requirement artifacts, resolve ambiguities, approve RAA output
- **QA Engineers** — review generated test cases, approve/edit scaffolds, export to automation frameworks

The critical interaction is the **review gate** — it must be fast, clear, and low-friction. If reviewing takes longer than writing tests manually, engineers will bypass the tool. Every screen is designed around minimizing time-to-decision at each gate.

---

## Information Architecture

```
/                           Dashboard — pipeline runs, confidence trends
/analyze                    New Analysis — submit artifacts
/requirements/:id           RAA Review — extracted requirements, ambiguities
/requirements/:id/tests     TGA Review — test case list, scaffold preview
/tests/:id                  Test Case Detail — full case, assertions, scaffold
/history                    Run history — filter by team, project, status
```

---

## Screen Designs

### 1. Dashboard

The entry point. Shows pipeline health at a glance and surfaces runs that need attention.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  QA Platform                                        [+ New Analysis]  [⚙]   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Needs Review (3)                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ● checkout-v2-prd     RAA Review     conf: 0.71  ▓▓▓▓▓▓▒▒▒▒  2h ago│   │
│  │ ● auth-redesign       Test Review    24 cases    P0:3 P1:8    1h ago│   │
│  │ ● payments-api-v3     RAA Review     conf: 0.68  ▓▓▓▓▓▓▒▒▒▒  30m ago│  │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  Recent Runs                                        [Filter ▾] [Export]    │
│  ┌──────────────────┬──────────┬──────────┬────────┬───────────┬────────┐  │
│  │ Name             │ Source   │ Status   │ Conf.  │ Tests     │ Age    │  │
│  ├──────────────────┼──────────┼──────────┼────────┼───────────┼────────┤  │
│  │ cart-redesign    │ PRD+JIRA │ ✓ Done   │  0.89  │ 31 cases  │ 2d ago │  │
│  │ search-v4        │ OpenAPI  │ ✓ Done   │  0.94  │ 18 cases  │ 3d ago │  │
│  │ notifications    │ Jira     │ ✗ Reject │  0.61  │ —         │ 4d ago │  │
│  │ onboarding-flow  │ PRD      │ ✓ Done   │  0.82  │ 42 cases  │ 5d ago │  │
│  └──────────────────┴──────────┴──────────┴────────┴───────────┴────────┘  │
│                                                                             │
│  Confidence Trend (30d)              Coverage by Type (last 10 runs)       │
│  1.0 ┤                               API  ████████████  34%               │
│  0.8 ┤  ╭──╮    ╭─╮   ╭──           Func ██████████████████  47%          │
│  0.6 ┤ ╭╯  ╰────╯ ╰───╯             Sec  █████  13%                       │
│  0.4 ┤─╯                             UI   ██  6%                           │
│      └───────────────────────                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key interactions:**
- "Needs Review" section is sticky at top — never scrolls away
- Clicking any row goes directly to the review screen
- Confidence bar is color-coded: green ≥ 0.80, amber 0.65–0.79, red < 0.65
- Trend chart shows per-team confidence improving over time (the key ROI signal)

---

### 2. New Analysis

Designed to accept messy, real-world inputs with minimal friction.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← Dashboard    New Analysis                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Project Name  [checkout-v2-redesign                              ]        │
│  Team          [Platform ▾]                                                 │
│                                                                             │
│  Attach Requirement Artifacts                                               │
│                                                                             │
│  ┌─ PRD / Design Doc ───────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │   Drag file here or paste text                  [Browse]             │  │
│  │                                                                       │  │
│  │   ┌────────────────────────────────────────────────────────────┐     │  │
│  │   │ ## Checkout V2 Redesign                                     │     │  │
│  │   │ ### Goals                                                   │     │  │
│  │   │ Reduce checkout abandonment by 15%...                      │     │  │
│  │   └────────────────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ Jira Stories ────────────────────────────────────────────────────────┐  │
│  │  Jira URL or paste exported JSON                                       │  │
│  │  [https://jira.example.com/browse/CART-                      ] [Fetch]│  │
│  │  ✓ CART-1201  ✓ CART-1202  ✓ CART-1203                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─ OpenAPI Spec ─────────────────────────────────────────────────────────┐  │
│  │  URL or file                                                            │  │
│  │  [https://api.example.com/openapi.yaml                       ] [Fetch] │  │
│  │  ✓ 14 endpoints resolved                                               │  │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  All inputs are optional — provide what you have.                          │
│                                                                             │
│                                    [Cancel]  [Run Analysis →]              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key interactions:**
- All three inputs are optional — the form accepts any combination
- Jira fetch resolves stories inline with checkmarks before submitting
- OpenAPI fetch validates and counts endpoints immediately
- "Run Analysis" triggers the RAA pipeline and redirects to a loading state
- Progress shown as skill stages complete: Parsing → Extracting → Enriching → Scoring

---

### 3. RAA Review ← most important screen

The review gate. Engineers need to understand what was extracted and decide in < 2 minutes.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← Dashboard    checkout-v2-redesign    RAA Review         [Export JSON]   │
├──────────────────────────┬──────────────────────────────────────────────────┤
│                          │                                                  │
│  SOURCE                  │  EXTRACTED REQUIREMENTS                         │
│  ─────                   │  ──────────────────────                         │
│  [PRD] [Jira] [OpenAPI]  │  Confidence  ██████████▒▒  0.82                 │
│                          │  12 requirements · 3 workflows · 7 rules        │
│  ## Checkout V2          │                                                  │
│  ### Goals               │  ┌──────────────────────────────────────────┐  │
│  Reduce abandonment...   │  │ ● REQ-001  P1  [FUNCTIONAL]              │  │
│                          │  │   User can add item to cart              │  │
│  ### Features            │  │   ✓ Cart count increments                │  │
│  **F-001 Cart UX**       │  │   ✓ Item persists across sessions        │  │
│  Users can add items...  │  └──────────────────────────────────────────┘  │
│  Acceptance:             │  ┌──────────────────────────────────────────┐  │
│  - Count increments      │  │ ● REQ-002  P1  [FUNCTIONAL]              │  │
│  - Items persist         │  │   Guest checkout without account         │  │
│                          │  │   ✓ Skip login step                      │  │
│  **F-002 Guest           │  │   ✓ Email capture at confirmation        │  │
│  Checkout**              │  └──────────────────────────────────────────┘  │
│  Unauthenticated users   │  ┌──────────────────────────────────────────┐  │
│  can complete checkout   │  │ ⚠ REQ-003  P2  [PERFORMANCE]             │  │
│  without creating an     │  │   Checkout response time                 │  │
│  account.                │  │   ✗ No threshold defined  ← AMB-001      │  │
│                          │  └──────────────────────────────────────────┘  │
│  [Source text scrolls]   │  [Show all 12 →]                               │
│                          │                                                  │
├──────────────────────────┤  AMBIGUITIES  (2 found, 0 blocking)            │
│  ENTITIES                │  ──────────────────────────────────────────     │
│  Cart, Order, User,      │  ┌──────────────────────────────────────────┐  │
│  PaymentService          │  │ ⚠ AMB-001  HIGH                          │  │
│                          │  │   REQ-003: No latency threshold defined  │  │
│  WORKFLOWS               │  │   Suggest: Define p95 target (e.g. 200ms)│  │
│  WF-001 Add to Cart      │  │   [Add clarification note]               │  │
│  WF-002 Guest Checkout   │  └──────────────────────────────────────────┘  │
│  WF-003 Payment          │  ┌──────────────────────────────────────────┐  │
│                          │  │ ○ AMB-002  MEDIUM                        │  │
│  BUSINESS RULES          │  │   REQ-007: Payment retry behavior unclear│  │
│  BR-001 Cart qty ≤ 99 *  │  │   [Add clarification note]               │  │
│  BR-002 Auth before pay  │  └──────────────────────────────────────────┘  │
│  * inferred              │                                                  │
└──────────────────────────┴──────────────────────────────────────────────────┤
│  [✗ Reject]   Reason: [                                          ]          │
│                                                  [✓ Approve & Generate Tests→]│
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key interactions:**
- Clicking a requirement in the right panel highlights its source text on the left (bidirectional link)
- Inferred business rules (`*`) are visually distinct — they're hypotheses, not facts
- Ambiguities have an inline "Add clarification note" that appends context to the requirement before approval — avoids a back-and-forth cycle
- Requirements can be edited inline (title, acceptance criteria) before approval
- "Approve" button is blocked if any `BLOCKING` ambiguities exist — must be resolved first
- Reject reason is required and becomes context for the re-run

---

### 4. TGA Review

Review generated test cases. The goal is fast triage, not reading every case in detail.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← RAA Review    checkout-v2-redesign    Test Review      [Export] [⚙]     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  31 cases generated    Coverage: 85%    [P0: 3] [P1: 9] [P2: 15] [P3: 4]  │
│  ████████████████████████████████████████████░░░░░░  Req coverage: 11/12   │
│                                                                             │
│  [All] [Functional] [API] [Security] [UI] [Edge]   [P0 first ▾]  [🔍 Search]│
├───────────────────────────────────────────┬─────────────────────────────────┤
│                                           │                                 │
│  □  [P0] [SECURITY]  TC-003              │  TC-003 Detail                  │
│     Auth: verify 401 on expired JWT      │  ─────────────────────────      │
│     REQ-008 · API                    [▾] │                                 │
│  ─────────────────────────────────────── │  Type    SECURITY               │
│  □  [P0] [SECURITY]  TC-007              │  Priority P0                    │
│     IDOR: order access by other user     │  Source   REQ-008               │
│     REQ-008 · API                        │                                 │
│  ─────────────────────────────────────── │  Preconditions                  │
│  □  [P0] [SECURITY]  TC-011              │  • User A is authenticated      │
│     Rate limit: 5 failed logins → 429   │  • User A owns order ORD-001    │
│     REQ-009 · API                        │  • User B is authenticated      │
│  ═══════════════════════════════════════ │                                 │
│  □  [P1] [FUNCTIONAL]  TC-001   ★       │  Steps                          │
│     Authenticated user adds item to cart │  1. User B requests GET         │
│     REQ-001 · Playwright scaffold        │     /api/v1/orders/ORD-001      │
│  ─────────────────────────────────────── │     with User B's JWT           │
│  □  [P1] [FUNCTIONAL]  TC-002            │  2. Verify response             │
│     Guest checkout — happy path          │                                 │
│     REQ-002 · Playwright scaffold        │  Expected                       │
│  ─────────────────────────────────────── │  • HTTP 403 Forbidden           │
│  □  [P1] [API]  TC-015                   │  • Body: {"error": "forbidden"} │
│     POST /orders — valid request         │                                 │
│     REQ-005 · pytest scaffold            │  Assertions                     │
│  ─────────────────────────────────────── │  ✓ STATUS_CODE = 403            │
│  □  [P2] [NEGATIVE]  TC-018              │  ✓ RESPONSE_BODY contains       │
│     Add out-of-stock item to cart        │    "forbidden"                  │
│     REQ-001                              │                                 │
│  ─────────────────────────────────────── │  ┌─ Scaffold ──────────────┐   │
│  ⊘  [P2] [EDGE_CASE]  TC-022  duplicate │  │ async def test_tc003_   │   │
│     Cart quantity at 99 (max)            │  │   idor_order_access(    │   │
│     REQ-001  ≈ TC-019                    │  │   client, user_b_token):│   │
│                                           │  │   resp = await client.  │   │
│  [Select All P0+P1]  [Deselect All]      │  │   get("/orders/ORD-001",│   │
│                                           │  │   ...)                  │   │
│                                           │  │   assert resp.status    │   │
│                                           │  │   == 403                │   │
│                                           │  └─────────────────────────┘  │
│                                           │  [Copy]  [Download .py]        │
├───────────────────────────────────────────┴─────────────────────────────────┤
│  27 selected (4 deselected — duplicates)                                    │
│  [✗ Reject]  [✗ Reject Selected]         [✓ Approve Selected] [✓ Approve All→]│
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key interactions:**
- P0 cases appear at the top, visually separated from P1+ by a divider
- Duplicate cases are greyed out and pre-deselected — engineers can still include them
- ★ marks cases with a generated scaffold — most valuable to the engineer
- Clicking a row opens the detail panel on the right without navigating away
- Scaffold code has syntax highlighting, a one-click copy, and a "Download .py" button
- "Select All P0+P1" is the fast path for most engineers — review the important ones, approve the rest
- Bulk approve/reject so engineers don't click 31 times

---

### 5. Export

After approval, engineers need to get test scaffolds into their repo fast.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Export Test Suite — checkout-v2-redesign                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Format                                                                     │
│  ● Playwright (Python)  tests/e2e/{feature}/                               │
│  ○ pytest               tests/api/{feature}/                               │
│  ○ Appium               tests/mobile/{feature}/                            │
│  ○ JSON (raw TestSuite)                                                     │
│  ○ CSV (for Jira import)                                                    │
│                                                                             │
│  Include                                                                    │
│  ☑ P0 cases (3)     ☑ P1 cases (9)                                         │
│  ☑ P2 cases (13)    ☐ P3 cases (4)                                         │
│  ☐ Duplicate cases                                                          │
│                                                                             │
│  Output                                                                     │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ tests/e2e/cart/                                                     │    │
│  │   test_add_to_cart.py       (TC-001, TC-018, TC-022)               │    │
│  │   test_guest_checkout.py    (TC-002, TC-023, TC-024)               │    │
│  │   conftest.py               (shared fixtures)                      │    │
│  │ tests/api/checkout/                                                 │    │
│  │   test_orders_api.py        (TC-015, TC-016, TC-017)               │    │
│  │ tests/security/                                                     │    │
│  │   test_auth.py              (TC-003, TC-007, TC-011)               │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  25 files · 22 test functions                                              │
│                                                                             │
│                          [Cancel]  [Download .zip]  [Copy git patch]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Critical Interaction: The Review Loop

The most common failure mode for AI-assisted tools is a slow review loop that erodes trust. The design addresses this:

```
                    Target time-to-decision per screen
                    ───────────────────────────────────
                    RAA Review:  < 3 minutes
                    TGA Review:  < 5 minutes (31 cases)

    How:
    - Ambiguities surface the exact problem and a suggested fix
    - Requirements are linked to source text (no re-reading the PRD)
    - P0 cases always appear first — approve the critical ones fast
    - Duplicate cases are pre-deselected (no busywork)
    - Inline clarification notes feed back into the next run
    - Bulk approve/reject — not 31 individual clicks
```

---

## Notification Design

Reviews pile up silently if there's no prompt. Two notification channels:

**In-app** — the Dashboard "Needs Review" section is always the first thing visible on load.

**Async** — webhook POST to Slack/Teams when a run enters `AWAITING_REVIEW`:

```
QA Platform
─────────────────────────────────────────────
checkout-v2-redesign  needs RAA review

Confidence: 0.71  |  2 ambiguities  |  12 reqs

[Review now →]  (expires in 7 days)
```

---

## Frontend Stack Recommendation

| Layer | Choice | Reason |
|-------|--------|--------|
| Framework | Next.js (App Router) | Server components for fast initial load; file-based routing matches URL structure |
| UI components | shadcn/ui + Tailwind | Unstyled primitives you own; not a locked-in component library |
| Code highlighting | Shiki | Server-side, zero flash, supports Python out of the box |
| Charts | Recharts | Simple enough for confidence trend + coverage bar |
| State | Zustand (client) + SWR (server) | Lightweight; SWR for polling pipeline status |
| Forms | React Hook Form + Zod | Shares Zod schemas with the FastAPI Pydantic models if you generate types |
| Type generation | `openapi-typescript` | Auto-generates TypeScript types from your FastAPI `/openapi.json` |

The bidirectional requirement ↔ source text linking on the RAA Review screen is the hardest UI problem. Implement it as highlight-on-hover using character offset ranges stored in the `source_reference` field of each `Requirement`.
