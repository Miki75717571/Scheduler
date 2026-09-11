# Cafeteria Shift Scheduler — Architecture & Build Plan

**Version:** 1.0 · **Date:** 2026-09-10

---

## 1. What this system actually is

Strip away the UI and this is three separate things glued together:

1. **A data collection app.** Employees tell you when they can work. This is boring CRUD and it is where 70% of your time saving comes from.
2. **A constraint solver.** Given availability + rules + scores, produce a legal, fair, well-staffed schedule. This is a real optimization problem with a well-known name: *nurse rostering*. It is NP-hard, so you do not write a clever loop — you describe the problem to a solver and let it search.
3. **A manager's override surface.** The solver is never right 100% of the time. The manager must be able to fix anything, and the system must tell them immediately when a fix breaks a rule.

The single most important architectural decision in this whole project is: **keep those three things separate.** In particular, the solver must be a pure function with no database access:

```
solve(slots, employees, availability, scores, rules, locked_assignments)
    -> (assignments, violations, diagnostics)
```

Everything goes in as plain data structures, everything comes out as plain data structures. If you get this right you can unit-test scheduling logic with fixture files in milliseconds, replay any past month, compare two algorithm versions on the same input, and swap the whole solver later without touching the app. If you get it wrong — solver reaching into the ORM, business rules scattered across API handlers — the project becomes unmaintainable at around month three. This is the mistake almost every homegrown scheduler makes.

---

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | Fast, standard, huge ecosystem |
| UI kit | Tailwind CSS + shadcn/ui | Calendar grids and dense tables without fighting a component library |
| Data fetching | TanStack Query | Cache, optimistic updates, refetch on window focus |
| Forms | react-hook-form + zod | Same zod schemas can mirror backend Pydantic validation |
| i18n | react-i18next, `pl` + `en` | Translation JSON files, language switcher, `pl` default |
| Backend | Python 3.12 + FastAPI | Typed, async, auto-generated OpenAPI docs |
| ORM | SQLAlchemy 2.0 + Alembic | Mature migrations; do not skip migrations even at the start |
| Validation | Pydantic v2 | Shared request/response contracts |
| Auth | JWT (access + refresh), argon2 password hashing | Refresh token in httpOnly cookie, access token in memory |
| **Solver** | **Google OR-Tools CP-SAT** | Free, best-in-class, Python-native. This is the reason to use Python at all. |
| Database | PostgreSQL 16 | Neon or Supabase free tier |
| Email | Resend (or Postmark) | Invites, schedule-published notifications, deadline reminders |
| Testing | pytest + Vitest + Playwright | Solver golden tests are the critical ones |

**Deployment topology:**

```
Browser ──► Vercel/Netlify (static React build)
                │  HTTPS, JWT
                ▼
        Fly.io / Railway / Render  (FastAPI container)
                │
                ├──► Neon Postgres
                └──► Resend (email)
```

Two deployment notes that will otherwise bite you:

- **The OR-Tools wheel is ~100 MB.** It does not fit comfortably in Vercel/Lambda serverless functions. Run the backend as a long-lived container (Fly.io, Railway, Render). This is why the backend is not serverless.
- **Solving takes seconds, not milliseconds.** Never solve inside a request/response cycle. Create a `schedule_run` row with status `PENDING`, kick off a background task, return `202 Accepted` + run ID, and let the frontend poll. Give CP-SAT a hard time limit (30s default, configurable) — it returns the best solution found so far, which is almost always excellent.

Expected cost at your size: **€0–20/month.**

---

## 3. Domain model

Names in `PascalCase` are tables. This schema is deliberately more general than "morning/evening" because you already said weekends differ and you will want to change staffing levels seasonally.

### 3.1 People and access

```
User
  id, email (unique), password_hash, full_name, phone
  role            : EMPLOYEE | MANAGER | ADMIN
  employment_type : FULL_TIME | PART_TIME | STUDENT | CASUAL
  contract_min_shifts, contract_max_shifts    (nullable overrides of global rules)
  locale          : 'pl' | 'en'
  is_active       : bool          -- deactivate, never delete; history must survive
  created_at, invited_at, activated_at

Invitation
  id, email, role, token_hash, expires_at, accepted_at, created_by_user_id
```

Employees never self-register. The manager sends an invite; the link carries a signed single-use token.

### 3.2 Shift structure

```
ShiftType
  id, code ('MORNING' | 'MIDDAY' | 'EVENING'), name_pl, name_en
  start_time, end_time       -- local wall-clock times, NOT timestamps
  color_hex
  active_weekdays : int bitmask (Mon=1 … Sun=64)
      MORNING -> all 7 days;  EVENING -> all 7 days;  MIDDAY -> Sat+Sun only
  default_required_staff, default_min_staff, default_max_staff
  sort_order
```

Making `MIDDAY` a row rather than an `if weekend` in code is what lets you add "Friday late shift" later without a deploy. That directly answers your "but this we would discuss later".

```
SchedulePeriod                 -- one calendar month
  id, year, month
  state : DRAFT
        | COLLECTING            -- employees can submit availability
        | LOCKED                -- deadline passed, availability frozen
        | GENERATED             -- solver has run, manager is editing
        | PUBLISHED             -- visible to employees, immutable except by manager
  availability_opens_at, availability_deadline
  published_at, published_by_user_id

ShiftSlot                      -- generated when the period is created: one row per (date, shift type)
  id, period_id, date, shift_type_id
  required_staff, min_staff, max_staff    -- copied from ShiftType, editable per day
  is_closed : bool                        -- holidays, renovation days
  note
```

`ShiftSlot` being a real row (not computed on the fly) is what lets the manager say "Christmas Eve we need 4 people in the morning and we're closed in the evening."

### 3.3 Availability

```
AvailabilitySubmission         -- one per (user, period)
  id, user_id, period_id
  status : NOT_STARTED | DRAFT | SUBMITTED
  submitted_at, last_edited_at

Availability                   -- one per (user, shift_slot)
  id, submission_id, shift_slot_id
  status : UNAVAILABLE | AVAILABLE | PREFERRED
  note                          -- "only until 20:00"
```

Three states, not two. `PREFERRED` costs the employee nothing extra to click but gives the solver far better information — it is the difference between "I can" and "I want to". Absence of a row means `UNAVAILABLE` (safe default).

### 3.4 Scoring

```
ScoreCriterion
  id, code ('CUSTOMER_SERVICE', 'RELIABILITY', 'SPEED', 'SENIORITY', …)
  name_pl, name_en, description
  weight    : decimal, all active weights sum to 1.0
  scale_min : 1, scale_max : 5
  is_active

EmployeeScore
  id, user_id, criterion_id, value (1–5)
  effective_from : date          -- never UPDATE in place; insert a new row
  set_by_user_id, note
```

Composite score, normalized to 0–100:

```
score(e) = 100 * Σ_c ( weight_c * (value(e,c) - 1) / (scale_max_c - 1) )
```

Versioning scores by `effective_from` means a schedule generated in March can always be explained with March's scores. You will want this the first time an employee asks "why did I get fewer shifts?".

**Scores are manager-only, at the query level.** No employee-facing endpoint may ever select from `EmployeeScore` or return a composite score. Enforce this in the repository layer, not in the UI — a hidden `<div>` is not access control.

### 3.5 Rules — as data, not code

```
Rule
  id, code, name_pl, name_en
  type       : enum (see below)
  scope      : GLOBAL | EMPLOYMENT_TYPE | USER
  scope_ref  : nullable employment_type or user_id
  params     : JSONB
  severity   : HARD | SOFT
  weight     : int          -- only meaningful for SOFT
  phase      : AVAILABILITY | SCHEDULE | BOTH
  is_active
```

Rule types to implement:

| Type | Params | Phase | Example |
|---|---|---|---|
| `MIN_AVAILABILITY_COUNT` | `{n: 7}` | availability | "declare at least 7 shifts" |
| `MIN_AVAILABILITY_IN_SET` | `{n:1, weekday:'FRI', shift:'EVENING'}` | availability | "at least 1 Friday evening" |
| `MIN_AVAILABILITY_WEEKEND` | `{n: 2}` | availability | "at least 2 weekend shifts" |
| `MIN_SHIFTS_PER_MONTH` | `{n: 5}` | schedule | contract floor |
| `MAX_SHIFTS_PER_MONTH` | `{n: 18}` | schedule | contract ceiling |
| `MAX_CONSECUTIVE_DAYS` | `{n: 5}` | schedule | fatigue |
| `MIN_REST_HOURS` | `{h: 11}` | schedule | blocks evening→next-morning |
| `ONE_SHIFT_PER_DAY` | `{}` | schedule | hard, always on |
| `MAX_WEEKEND_SHIFTS` | `{n: 3}` | schedule | fairness |
| `FAIR_DISTRIBUTION` | `{max_spread: 3}` | schedule | soft, balances totals |
| `REQUIRE_SENIOR_ON_SHIFT` | `{min_score: 60, count: 1}` | schedule | at least one strong person per shift |

That last one is quietly the most valuable rule you have, and it is the *right* way to use scoring — it guarantees shift quality rather than just rewarding favourites.

The same `Rule` rows drive two different things:

- **`AVAILABILITY`-phase rules** are checked when an employee presses *Submit*. A `HARD` failure blocks submission with a clear message ("You still need 1 Friday evening"). Show progress live as they fill the calendar, so submission never fails as a surprise.
- **`SCHEDULE`-phase rules** are (a) encoded into the solver and (b) re-checked by an independent validator against the final schedule, including after manual edits.

Write the validator separately from the solver even though it duplicates logic. The solver tells you what it *intended*; the validator tells you what is *true* right now. When the manager drags someone into a Sunday evening, only the validator runs.

### 3.6 Assignments and runs

```
ScheduleRun
  id, period_id, algorithm_version, params_snapshot JSONB
  status : PENDING | RUNNING | SUCCESS | FAILED
  objective_value, solve_time_ms, solver_status, stats JSONB
  created_at, created_by_user_id

Assignment
  id, shift_slot_id, user_id, schedule_run_id (nullable)
  source    : AUTO | MANUAL
  is_locked : bool     -- manager pinned this; solver must respect it on re-run
  created_at, created_by_user_id

Violation                       -- recomputed on every change
  id, period_id, severity : ERROR | WARNING
  rule_code, message_key, message_params JSONB
  shift_slot_id (nullable), user_id (nullable)

AuditLog
  id, actor_user_id, action, entity_type, entity_id, before JSONB, after JSONB, at
```

`is_locked` is what makes re-running the solver safe. Manager fixes three problem days, hits *Regenerate*, and their three fixes survive while everything else re-optimizes around them.

`AuditLog` matters more than it looks: when an employee disputes a shift, you need to know whether the algorithm or a human put them there.

---

## 4. The scheduling algorithm

### 4.1 Formulation

Boolean decision variable `x[e][s] = 1` if employee `e` works slot `s`.

**Hard constraints** (the schedule is invalid without them):

```
x[e][s] = 0                                   if availability(e,s) = UNAVAILABLE
x[e][s] = 1                                   if locked assignment exists
Σ_{s ∈ day(d)} x[e][s] ≤ 1                    one shift per person per day
x[e][evening_d] + x[e][morning_{d+1}] ≤ 1     minimum rest
Σ_e x[e][s] ≤ max_staff[s]                    never overstaff
Σ_s x[e][s] ≤ contract_max[e]                 contract ceiling
max consecutive working days                   sliding window over each (n+1)-day span
```

**Understaffing is soft, not hard.** This is the crucial modelling decision:

```
under[s] ≥ required_staff[s] - Σ_e x[e][s],   under[s] ≥ 0
```

If understaffing were hard, one impossible Sunday would make the entire month `INFEASIBLE` and the solver would return nothing. Modelled as a heavily-penalized soft variable, the solver instead fills everything it can and hands you `under[s] > 0` for the bad days — which is *exactly* the red tile you described in the manager calendar. The solver's failure output becomes the feature.

**Objective — minimize:**

```
  W_UNDER      · Σ_s under[s]                        W_UNDER = 10000
+ W_MIN_SHIFT  · Σ_e shortfall_below_contract_min[e] W = 1000
+ W_PREF       · Σ_{e,s} (1 - x[e][s]) · is_preferred(e,s)   W = 20
+ W_FAIR       · (max_e workload_e - min_e workload_e)       W = 30
+ W_UNPOPULAR  · spread of weekend/Friday-evening shifts      W = 25
- W_SCORE      · Σ_{e,s} normalized_score(e) · x[e][s] · desirability(s)  W = 10
- W_DEBT       · Σ_e preference_debt(e) · granted_preferences(e)          W = 15
```

Weights live in a config table so you can tune them without a deploy.

### 4.2 On "priority to the higher-scoring employees"

Your instinct is right but pure score-ranked greedy assignment fails in three predictable ways, and it is worth designing around them from day one:

1. **The rich get richer.** Top scorers take every good shift; low scorers fall below their contract minimum, earn too little, get demotivated, score lower, and the loop tightens. Your best people also burn out from over-scheduling.
2. **It ignores availability scarcity.** A high scorer available 20 days and a low scorer available only 8 should not compete on score alone — the constrained person should be placed first or they end up with nothing.
3. **Score is a weak signal.** A 1–5 manual rating has maybe ±1 of noise. Treating it as a strict ordering gives it far more authority than it has earned.

The formulation above handles all three: score enters as a *weighted term in the objective*, competing against fairness and coverage, rather than as a sort order. In practice this means high scorers reliably win **contested desirable shifts** (Friday evening, Saturday midday) while everyone still reaches their contract minimum. That is what you actually want.

Add a `preference_debt` counter per employee: increment when someone's `PREFERRED` slot is denied, decrement when granted, carry it across months. It costs one integer column and it single-handedly kills the "the app always screws me" complaint.

### 4.3 "Optimize the assessment and the algorithm itself"

You do not need machine learning, and you should not start with it. You need a feedback loop:

**Every manual correction is a labelled training example.** When the manager removes employee A from slot S and inserts employee B, that is a statement that the model was wrong. Log it (`AuditLog` already does), then build a `/manager/insights` page showing:

- Corrections per generated schedule, over time. **This is your single north-star metric.** It should trend toward zero. If it does not, the rules or weights are wrong, not the solver.
- Which rule or weight each correction most likely conflicted with.
- Which employees are corrected *into* shifts most often (their score is too low) and *out of* most often (too high). Show this next to their current scores as a suggestion: "Anna is manually added to evening shifts 4× more than assigned — consider raising her Customer Service score."
- Coverage rate, average preference satisfaction, fairness spread per month.

After a few months of data you can fit the weights properly (a simple least-squares or grid search over the weight vector, scored by "how few corrections would this weighting have needed?"). Keep it offline, keep it explainable. A manager who cannot explain why the schedule looks the way it does will stop trusting it, and an untrusted scheduler is worse than a spreadsheet.

### 4.4 Determinism and testing

CP-SAT can return different equally-optimal solutions between runs. For tests, set `random_seed` and `num_search_workers=1`. Assert **invariants**, not exact rosters:

- no employee assigned twice in one day
- no assignment where availability is `UNAVAILABLE`
- all `HARD` rules satisfied
- coverage ≥ known-optimal for the fixture
- locked assignments preserved

Build a fixture library of nasty months: everyone wants mornings; one person available only on Fridays; a public holiday; two people quit mid-month; a month that genuinely cannot be fully staffed. These golden tests are the highest-value tests in the codebase.

---

## 5. Permissions

| Capability | Employee | Manager | Admin |
|---|---|---|---|
| Submit/edit own availability (while `COLLECTING`) | ✅ | ✅ | ✅ |
| See own published schedule | ✅ | ✅ | ✅ |
| See colleagues' names on shifts they share | ✅ | ✅ | ✅ |
| See colleagues' availability | ❌ | ✅ | ✅ |
| See any score, own or others' | ❌ | ✅ | ✅ |
| See who has/hasn't submitted | ❌ | ✅ | ✅ |
| Edit assignments, run solver, publish | ❌ | ✅ | ✅ |
| Manage users, rules, criteria, weights | ❌ | ❌ | ✅ |

Note the deliberate choice: employees see **their own score not at all**. Exposing a 1–5 "customer service" rating to staff turns a scheduling tool into a performance-review tool and will cause you problems you do not want. If you later decide to show it, make it an explicit per-criterion `is_visible_to_employee` flag.

Two independent enforcement layers: a FastAPI dependency (`require_role`) on every route, and repository methods that take the acting user and filter rows. Never rely on the frontend.

---

## 6. Screens

**Employee (3 screens, that's all):**

1. *My availability* — month calendar, each day a tile with 2 or 3 toggle chips cycling `—` / `available` / `preferred`. A live requirements bar at the top: "7/7 shifts ✅ · Friday evening 0/1 ❌". Bulk actions ("all mornings", "clear weekends") — without these people will not fill it in. Big **Submit** button, disabled with an explanatory tooltip until hard rules pass.
2. *My schedule* — published month, own shifts highlighted, plus who else is on. Export to iCal/Google Calendar.
3. *Profile* — name, phone, password, language.

**Manager:**

1. *Period dashboard* — state machine controls (open collection → set deadline → lock → generate → publish), submission tracker with one-click reminder to laggards.
2. *Schedule calendar* — the core screen. Month grid, each day split into shift lanes, employee chips. **Colour by status: green = fully staffed, amber = understaffed but legal, red = below minimum or rule violation.** Drag-and-drop between slots, click to lock a chip, side panel listing every current violation with a jump link. Filter by employee to see one person's month.
3. *Generate* — pick a run, see progress, view diagnostics ("Sunday 14 evening: only 1 of 3 staff available"), regenerate with locks preserved, compare against previous run.
4. *Employees* — list, scores, criterion editing with score history.
5. *Insights* — the corrections/coverage/fairness metrics from §4.3.
6. *Settings (admin)* — shift types, staffing levels per weekday, rules, criteria weights, solver weights.

---

## 7. Traps specific to this domain

- **Never store shift times as UTC timestamps.** Store `date` + local `time`. A UTC timestamp turns the DST change nights (late October, late March) into a source of off-by-one-hour bugs and phantom shifts. Convert to a timestamp only when exporting to iCal.
- **Deactivate, never delete, employees.** Foreign keys to past assignments must survive; history is your dispute-resolution record.
- **Employees will edit availability after the deadline.** They will ask. Give the manager an explicit "reopen for this person" action rather than letting them do it by hand in the database.
- **Publishing must be a hard boundary.** Once published, changes generate a notification, because someone has already planned their month around it.
- **Mobile first for the employee panel.** Every employee will fill this in on a phone, standing up, in under two minutes. If it takes longer they will go back to messaging you.
- **Availability defaults to unavailable.** Never assume silence means "can work".

---

## 8. Build order

Each phase is independently useful — you can stop after any of them and still be better off than you are today.

| Phase | Contents | Value delivered |
|---|---|---|
| **0** | Monorepo, Docker Compose, Postgres, migrations, CI, health check | Foundation |
| **1** | Auth, invites, roles, user CRUD, i18n scaffold | Login works |
| **2** | Shift types, periods, slot generation, employee availability UI, availability-phase rules, submission tracker | **Biggest single win — no more chasing people over WhatsApp** |
| **3** | Manager calendar, manual assignment, validator, violation highlighting, publish, employee schedule view | Full manual scheduler, faster than your spreadsheet |
| **4** | Criteria, scores, score history | Data for the solver |
| **5** | CP-SAT solver, background runs, generate/regenerate, locks, diagnostics | Automatic scheduling |
| **6** | Email notifications, iCal export, PDF/Excel export, insights dashboard, shift swaps | Polish |

**Ship phases 0–2 first and use them for one real month before writing a line of solver code.** You will learn things about your own rules that no amount of upfront design would have surfaced, and the solver you then build will be the right one.

---

## 9. Repository layout

```
cafeteria-scheduler/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            config, security, deps, i18n message keys
│   │   ├── db/              session, base, migrations/ (alembic)
│   │   ├── models/          SQLAlchemy models
│   │   ├── schemas/         Pydantic DTOs
│   │   ├── repositories/    all DB access, permission-aware
│   │   ├── services/        use cases (period_service, availability_service, …)
│   │   ├── rules/           rule definitions, availability_validator, schedule_validator
│   │   ├── scheduling/      ← PURE. no DB imports allowed here.
│   │   │   ├── domain.py    frozen dataclasses: SolverInput, SolverOutput
│   │   │   ├── cpsat.py     the CP-SAT model
│   │   │   ├── weights.py
│   │   │   └── explain.py   human-readable diagnostics
│   │   └── api/v1/          routers
│   └── tests/
│       ├── unit/
│       ├── scheduling/      golden fixture tests  ← the important ones
│       └── api/
├── frontend/
│   └── src/{api,components,features,hooks,i18n,pages,lib}
├── docker-compose.yml
├── ARCHITECTURE.md
└── README.md
```

Enforce the purity of `scheduling/` with a test that fails if anything under it imports `sqlalchemy`, `app.models`, or `app.db`. It sounds pedantic; it is the guardrail that keeps this project maintainable.
