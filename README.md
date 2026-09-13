# Cafeteria Shift Scheduler

Shift scheduling for a ~15–25 person cafeteria: employees submit monthly availability, a CP-SAT
solver generates a fair, legal, well-staffed schedule, a manager reviews/fixes/publishes it.

- **Design & rationale:** [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- **How we build it day to day:** [`CLAUDE.md`](./CLAUDE.md)

## Quick start

Requires [Python](https://www.python.org/downloads/) 3.12+ and [Node.js](https://nodejs.org/) 20+
on your PATH. Nothing else — no Docker, no database server, no `.env` file, no admin rights.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

(The `-ExecutionPolicy Bypass` is needed because Windows blocks running local `.ps1` scripts by
default — it only affects this one process, not your system-wide policy.)

This installs dependencies, runs migrations, seeds a bootstrap admin account, starts the backend
and frontend (each in its own window), and opens the app in your browser, printing the admin
login to the terminal. It's safe to run again any time — re-running skips whatever's already done
and reuses whatever's already running.

By default the app runs entirely against a local SQLite file at `backend/.dev/db.sqlite3`, with
JWT/session secrets auto-generated on first run and cached in `backend/.dev/secrets.json` (both
gitignored) — nothing to create or fill in yourself. See [Using Postgres / Supabase](#using-postgres--supabase)
below for pointing this at a real database instead, which you'll want before deploying.

## Running the pieces by hand

Same zero-config defaults apply; this is just what `start.ps1` automates.

**Backend** (from `backend/`):
```bash
uv sync
uv run alembic upgrade head
uv run python -m app.seed      # prints the admin email/password
uv run uvicorn app.main:app --reload
```

**Frontend** (from `frontend/`):
```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
cd backend && uv run pytest
cd frontend && npm run test -- --run
```

Backend tests run against a second SQLite file (`backend/.dev/test.sqlite3` by default), created
and torn down automatically — they never touch your dev database. Each test also runs inside a
rolled-back transaction, so state doesn't leak between tests either.

## Other commands

**Backend** (from `backend/`):
```bash
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy .                  # type check
uv run alembic revision --autogenerate -m "..."  # new migration
```

**Frontend** (from `frontend/`):
```bash
npm run lint        # eslint
npm run format       # prettier
npm run typecheck    # tsc --noEmit
```

## Using Postgres / Supabase

The app fully supports Postgres — nothing about switching to it requires a code change, only an
environment variable. Set `DATABASE_URL` (as a real env var, or in a `.env` file at the repo root)
to a Postgres connection string and it's used unchanged; SQLite's zero-setup default only applies
when `DATABASE_URL` is unset.

**Deploying against Supabase:** use the **Session pooler** connection string (port `5432`, IPv4
compatible) — copy it exactly as Supabase shows it (`postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`).
Two other options on that same page will *not* work here and are easy to grab by mistake:

- **Direct connection** — IPv6-only; unreachable from most local networks and many hosting
  platforms.
- **Transaction pooler** (port `6543`) — breaks Alembic migrations (no persistent session for
  `CREATE TYPE`/DDL sequencing) and breaks asyncpg's prepared statements (each request can land on
  a different backend connection, and a statement prepared on one isn't valid on another).

The Session pooler holds one real Postgres connection per client for the life of the session,
which is what both Alembic and asyncpg need. `sslmode`/prepared-statement handling for asyncpg is
already taken care of (see `backend/app/core/config.py`).

For production, also set `APP_ENV=production` — **the app refuses to start unless every secret
below is provided explicitly**; nothing dev-only (auto-generated secrets, SQLite) can leak
through:

```
APP_ENV=production
DATABASE_URL=<your Supabase Session pooler URL>
JWT_ACCESS_SECRET=<a real random secret>
JWT_REFRESH_SECRET=<a real random secret>
INVITATION_TOKEN_SECRET=<a real random secret>
ADMIN_BOOTSTRAP_PASSWORD=<a real password>
```

`backend/tests/unit/test_config.py` asserts this refusal happens.

## Phase 0 — what to click through

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1`
2. `curl http://localhost:8000/api/v1/health` → `{"status": "ok"}`
3. Open http://localhost:5173 → header shows a "Backend is reachable" badge.
4. CI (`.github/workflows/ci.yml`) runs lint/typecheck/test for both backend and frontend,
   including the `pl`/`en` locale-key-parity check (`frontend/src/i18n/i18n.test.ts`) and the
   `backend/app/scheduling/` purity guard (`backend/tests/scheduling/test_purity.py`).

## Phase 1 — what to click through

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1` (creates the bootstrap admin on first
   run and prints its login).
2. Go to http://localhost:5173/login, sign in as the bootstrap admin.
3. Invite yourself a second time with a different email via the API (no admin UI screen yet —
   that's a Phase 2+ concern once there's more to manage):
   ```bash
   curl -X POST http://localhost:8000/api/v1/invitations \
     -H "Authorization: Bearer <access_token from login response>" \
     -H "Content-Type: application/json" \
     -d '{"email": "newhire@example.com", "role": "EMPLOYEE"}'
   ```
4. Since `EMAIL_PROVIDER=console` by default, the invite link is logged to the backend window's
   console instead of actually emailed. Copy the `accept-invitation?token=...` URL.
5. Open that URL in the browser, set a name and password, submit.
6. Log out, log back in as the new employee.
7. Confirm authorization boundaries: as the employee, `GET /api/v1/users` and
   `POST /api/v1/invitations` both return 403. `backend/tests/api/test_users.py` and
   `test_invitations.py` assert this for every role combination.

## Phase 3 (backend) — what to click through

Assignments, the schedule validator, and the publish flow, exercised directly through `/docs`
(Swagger UI) against the demo data `app.seed` creates — see the next section for the calendar UI
built on top of this API.

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1`, then open
   http://localhost:8000/docs and click **Authorize** with the admin login the terminal printed
   (or `POST /api/v1/auth/login` and paste the `access_token` in as a Bearer token).
2. `GET /api/v1/periods` — find the period in state `GENERATED` for the current month (the
   `COLLECTING` one is next month's availability-collection demo from Phase 2). Copy its `id`.
3. `GET /api/v1/periods/{period_id}/violations` — the seeded month deliberately contains:
   - an `ERROR` with `rule_code: min_11h_rest` (an employee closes one evening then opens the
     next morning — 8 hours of rest against an 11-hour rule),
   - a `WARNING` with `rule_code: min_5_shifts_per_month` and `"required": 10` (one employee has
     a personal `contract_min_shifts` override stricter than the global default — their 6 shifts
     clear the global rule but not their own contract),
   - several `ERROR`s with `message_key: schedule.understaffed_below_minimum` (most of the month
     is intentionally left unassigned — this is a partially-scheduled month, not a finished one),
   - `WARNING`s with `message_key: schedule.assigned_despite_unavailable` (every seeded assignment
     was made without a matching availability declaration — allowed, just flagged).
4. `GET /api/v1/periods/{period_id}/assignments` — the handful of manual assignments behind those
   violations, each with `source: MANUAL`, `is_locked`, `created_by_user_id`.
5. Pick any `shift_slot_id` from `GET /api/v1/periods/{period_id}/slots` and call
   `GET /api/v1/periods/{period_id}/slots/{shift_slot_id}/available-employees` — employees who
   declared `AVAILABLE`/`PREFERRED` for it, already excluding anyone a `HARD` schedule rule would
   make impossible to add (e.g. already working another shift that day).
6. `POST /api/v1/periods/{period_id}/assignments` with a `shift_slot_id` + `user_id` — the
   response includes the freshly recomputed `violations` list, so a manager UI never needs a
   second round-trip after a change. `PATCH .../assignments/{id}/move`,
   `PATCH .../assignments/{id}/lock`, `DELETE .../assignments/{id}`, and
   `POST .../assignments/bulk` (several ops in one call) all work the same way.
7. `PATCH /api/v1/periods/{period_id}/state` with `{"state": "PUBLISHED"}` — refused with
   `409 period.publish_blocked_by_errors` while the `ERROR`-severity violations above exist.
   Retry with `{"state": "PUBLISHED", "override_violations": true}` to publish anyway.
8. `GET /api/v1/periods/{period_id}/audit-log` — every mutation above, plus the
   `period.publish_override` entry from the previous step, each with actor/before/after/when.
9. Log in as an employee (`employee01@example.com` / `password123`, see `app/seed.py`) and confirm
   `GET /api/v1/periods/{period_id}/assignments` returns 403 before publish, and — once
   published — only that employee's own shifts plus colleagues sharing them (no one else's, no
   availability, no scores); `GET /api/v1/periods/{period_id}/violations` and `.../audit-log` stay
   403 for that token regardless of publish state.
   `backend/tests/api/test_assignments.py` and `tests/unit/test_schedule_validator.py` assert all
   of the above.

## Phase 3 (frontend) — what to click through

The manager schedule calendar and the employee schedule view, on top of the API above.
`AssignmentRead` now also carries `full_name` (resolved server-side, scoped to just the users in
the response — see `app/repositories/user_repository.py`'s `list_by_ids`), which is what lets the
employee view name colleagues on a shared shift without a roster-wide endpoint.

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1`, then run `uv run python -m app.seed`
   from `backend/` if you haven't already — it seeds a `GENERATED` period for the current month
   with the three violation scenarios described above.
2. Log in as the manager/admin the terminal printed, go to **Manager** → the `GENERATED` period →
   **Open schedule calendar** (or go straight to `/manager/periods/{id}/schedule`).
3. Click any **+ Add** in an empty (red) lane — the picker opens. With no availability seeded for
   this month, everyone falls into the collapsed **Not marked available** section with its warning
   banner; expand it and pick someone anyway (the "exception" path). The chip appears immediately,
   the lane recolours (red → amber, since headcount and legality both feed the colour), and the
   violations panel on the right updates in place — no reload.
4. Click a chip once to lock it (thicker border, 🔒, remove disabled); click again to unlock.
   Remove an unlocked chip via its **×** — an "Undo" banner appears for a few seconds.
5. Drag a chip from one lane to another (desktop only — the calendar itself is desktop-first,
   unlike every other screen in the app).
6. Click any row in the **Violations** panel — the grid scrolls to and briefly highlights the day
   it concerns (or, for month-wide rules like `MAX_SHIFTS_PER_MONTH`, selects that employee in the
   filter instead).
7. Use **Filter to employee** to see one person's month and their shift count.
8. Click **Publish schedule** — since `ERROR`-severity violations exist, the confirm step asks you
   to publish anyway (`override_violations`, same as the API above). After publishing, edit an
   assignment again: its chip gets a blue ring and the header shows "N shift(s) changed since
   publish" — both read `Assignment.modified_after_publish`.
9. Click **Print** (or your browser's print preview) — the header, filter, picker, and side panel
   disappear; only the grid remains, landscape, one page.
10. Log in as `employee01@example.com` / `password123` and open **My schedule** (mobile-first —
    try a narrow viewport). Own shifts are listed with total count at the top, colleagues on shared
    shifts are named, and the shift you just re-edited after publish is marked "Changed since
    publish".
11. Confirm employees never reach the manager calendar: the **Manager** nav link is gone, and
    `/manager/periods/{id}/schedule` redirects to `/availability`.

Component tests: `frontend/src/features/schedule/{colorLogic,AssignPickerDialog,ViolationsPanel}.test.tsx`.

## Phase 4 — what to click through

Score criteria, versioned employee scores, and the manager scoring grid — data for the Phase 5
solver, no automatic assignment yet. `app.seed` creates four default criteria (customer service,
reliability, speed, seniority — weights `0.35/0.35/0.15/0.15`, all editable/replaceable by an
admin) and some demo scores; a few employees are deliberately left unscored on one criterion so
the grid's "not yet rated" state has something to show.

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1`, then run `uv run python -m app.seed`
   from `backend/` if you haven't already.
2. Log in as the bootstrap admin and open **Criteria** (`/admin/criteria`, admin-only nav link) —
   the four seeded criteria, each with its own rename/description save button, a weight input, and
   an **Active** checkbox. The **Active weights total** line updates live as you type and turns
   green once it hits exactly `1.0000`.
3. Try changing one weight without adjusting any other, then **Save weights** — rejected with
   `422 score_criterion.weights_must_sum_to_one` and the exact current total in the message. Adjust
   a second criterion's weight in the same table so they sum to `1.0` again and save — succeeds.
4. Add a new criterion (code/name only) — it's created **inactive** at weight 0 (an active weight
   change needs a coordinated multi-row save, so a brand-new criterion can never land on its own
   and break the sum). Give it a weight, uncheck an existing criterion or rebalance the others so
   the total is `1.0`, and save weights again to bring it live.
5. Log in as a manager (or stay admin) and open **Scores** (`/manager/scores`) — employees as rows,
   active criteria as columns, a composite column. Click a 1–5 button in any cell: it saves
   immediately (no separate "save" step) and shows a brief "Saved" indicator under the cell. A
   criterion with no value yet shows "Not yet rated"; an employee missing any active criterion
   shows `—` for composite rather than a misleading partial score.
6. Click **History** on any employee — a timeline of every score ever set for them, each entry
   showing the criterion, the value it replaced (or "First rating" if none), who set it, when, and
   any note. Score twice in a row on the same criterion via the grid and reopen History to see both
   entries — nothing is ever overwritten, only inserted (`app/models/employee_score.py`).
7. **Privacy — the most important part.** Log in as `employee01@example.com` / `password123` and
   confirm: `GET /api/v1/scores/grid`, `GET /api/v1/users/{any_id}/scores/history`, and
   `POST /api/v1/users/{any_id}/scores` all return `403`, including for the employee's own id.
   `GET /api/v1/users/me` and `GET /api/v1/users` (as admin) never contain a `score` field anywhere
   in the payload. There's also no **Scores**/**Criteria** link in the nav for that account, and
   `/manager/scores` / `/admin/criteria` redirect away if typed directly.
   `backend/tests/api/test_scores.py` asserts all of the above (weight-sum validation on both
   create/update/deactivate/bulk paths, versioning, and the full privacy boundary); the composite
   formula and weight-sum invariant also have standalone unit tests in
   `backend/tests/unit/test_score_service.py`, and the grid component in
   `frontend/src/features/scores/ScoringGrid.test.tsx`.

## Phase 5 (solver core, backend) — what to click through

The CP-SAT solver itself (`backend/app/scheduling/` — pure, no DB access, guarded by
`backend/tests/scheduling/test_purity.py`) plus the background-run plumbing around it, exercised
directly through `/docs` (Swagger UI). See the next section for the **Generate** screen built on
top of this API.

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1`, then run `uv run python -m app.seed`
   from `backend/` if you haven't already.
2. Open http://localhost:8000/docs and **Authorize** as the admin the terminal printed.
3. `GET /api/v1/periods` — find the `COLLECTING` period (next month's availability demo from
   Phase 2). `PATCH /api/v1/periods/{id}/state` with `{"state": "LOCKED"}` — the solver only runs
   against `LOCKED` or `GENERATED` periods (trying it on `DRAFT`/`COLLECTING` returns
   `409 schedule_run.period_not_ready`).
4. `POST /api/v1/periods/{period_id}/schedule-runs` with `{}` — returns `202` immediately with the
   run `id` and `status: "PENDING"`; the actual solve happens in a background task (never inside
   the request, per `CLAUDE.md` "Running it"), so on real data it'll typically already be
   `SUCCESS` by the time you poll it a moment later.
5. `GET /api/v1/schedule-runs/{run_id}` — poll until `status` is `SUCCESS` (or `FAILED`, with
   `error_message` set). On success: `objective_value`, `solve_time_ms`, `solver_status`
   (`OPTIMAL`/`FEASIBLE` — never `INFEASIBLE`, see ARCHITECTURE.md ss4.1), `stats` (coverage %,
   preference satisfaction rate, fairness spread, shifts per employee), and `diagnostics` (every
   understaffed slot and every employee below their contract minimum, as message keys + params).
6. `GET /api/v1/periods/{period_id}/assignments` — the solver's picks, `source: AUTO`. Lock one
   (`PATCH .../assignments/{id}/lock`), then `POST .../schedule-runs` again — the locked
   assignment survives the regeneration untouched; everything else is re-optimized around it.
7. `GET /api/v1/periods/{period_id}/schedule-runs` — every run for this period, newest first, so a
   manager can compare a regenerate against what it replaced.
8. `GET /api/v1/solver/weights` (admin-only — `403` for a manager token) — the live, tunable
   objective coefficients (ARCHITECTURE.md ss4.1's `W_UNDER`/`W_MIN_SHIFT`/etc). `PUT` a new set
   and re-run the solver — the next run's `params_snapshot` reflects the change; past runs keep the
   weights they actually used, frozen at creation time.
9. The solver golden fixtures are the real proof this phase works —
   `backend/tests/scheduling/test_cpsat_golden.py`: a normal month, everyone wanting mornings, one
   person available only Fridays, a closed holiday, a genuinely impossible month (still returns a
   usable schedule with red-tile diagnostics, never `INFEASIBLE`), a high scorer winning a
   contested shift while a low scorer still reaches their contract minimum, `preference_debt`
   breaking a tie, and locked assignments surviving even a pre-existing manager lock conflict.
   `backend/tests/api/test_schedule_runs.py` covers the same invariants through the real DB layer
   (background-task lifecycle, role enforcement, lock preservation on regenerate).

**One deliberate deviation worth knowing about:** `Rule.severity` (HARD/SOFT) governs the
schedule-phase *validator* (ARCHITECTURE.md ss3.5 — checked independently, after the fact); the
*solver*'s hard/soft split is fixed by rule type per ARCHITECTURE.md ss4.1 regardless of each
rule's configured severity (e.g. `MAX_CONSECUTIVE_DAYS` is seeded `SOFT` for the validator's
purposes but is always a hard sliding-window constraint inside the solver). This mirrors the
validator/solver duplication the codebase already documents ("the solver tells you what it
*intended*; the validator tells you what is *true* right now") but is easy to miss since both read
from the same `Rule` rows.

## Phase 5 (frontend) — what to click through

The **Generate** flow on top of the API above: a button on the manager schedule calendar, a
before/after confirmation so regenerating never silently discards manual work, a one-click revert,
translated diagnostics, run history with before/after comparison, and an admin screen for tuning
the solver's objective weights in plain language.

1. `powershell -ExecutionPolicy Bypass -File .\start.ps1`, then run `uv run python -m app.seed`
   from `backend/` if you haven't already — it seeds a `COLLECTING` period for **next month** with
   a full month of plausible availability already filled in for most employees (see
   `app/seed.py`'s `_seed_demo_period`).
2. Log in as the manager/admin the terminal printed, open **Manager**, click into that `COLLECTING`
   period, and click **Lock availability** (the solver only runs against `LOCKED`/`GENERATED`
   periods — the **Generate schedule** button stays disabled with an explanation on any earlier
   state, and again once the period is `PUBLISHED`).
3. Click **Open schedule calendar**. At the top, the **Generate schedule** section: since this
   period has no assignments yet, confirming shows "There are no existing assignments to lose."
   Click **Generate**.
4. Watch the status line move `Queued…` → `Solving… this can take up to 30s.` → `Schedule
   generated.` — the calendar below fills in **in place**, no reload. Against the seeded demo data
   this typically lands at **100% coverage** (30+ employees against ~70 shifts is generous) with a
   **preference satisfaction** somewhere in the 70–80% range; a couple of employees who were left
   in `NOT_STARTED`/`DRAFT` (never declared any availability — see `app.seed`'s
   `_DRAFT_ONLY_COUNT`) show up in **Below contract minimum** with 0 assigned shifts, which is also
   why the **fairness spread** number can look large — it's driven entirely by those two, not by
   the solver favouring anyone unfairly among people who actually declared availability. The
   shifts-per-employee bars make this legible at a glance instead of just a single spread number.
5. If **Understaffed shifts** appears under **Why the schedule looks like this**, click a listed
   date to jump the calendar to it, or click the **?** button on any red/amber lane directly — the
   dialog lists everyone who was available but not used, each with a reason (`Already working a
   MORNING shift that day`, `Already at their contract maximum of N shifts`, a rest-hours shortfall,
   or — when no rule stood in the way — `Available, but another candidate was prioritised`).
6. Click any solver-generated chip (dashed border, `A` badge) — the detail dialog confirms
   `Automatically assigned by the solver`, whether that person was `AVAILABLE`/`PREFERRED`, and
   that it isn't locked yet.
7. Hover a chip and click its 🔒 to lock it, then click **Regenerate schedule** — the confirmation
   now reads "1 locked assignment(s) will be kept" and "N unlocked assignment(s) will be discarded
   and replaced." Confirm: the locked chip survives untouched; everything else is re-optimized
   around it, exactly like the API-level test in the previous section.
8. Under the just-finished run's results, click **Revert to before this run** and confirm — the
   calendar snaps back to exactly what it was right before that regeneration (here, just your one
   locked chip), proving the "protect my manual work" safety net without needing the database.
9. Scroll to **Run history** — every run for this period, newest first, with objective value and
   solve time. Click **View** on the older run: a **Compared to the previous run** block appears
   showing coverage/preference/fairness deltas with `better`/`worse`/`unchanged` labels.
10. As an admin, open **Scheduling weights** (`/admin/solver-weights`, admin-only nav link) — each
    of the seven objective coefficients from ARCHITECTURE.md ss4.1 with a plain-language label and
    explanation (never the raw `W_FAIR`-style name). Change one, **Save weights**, generate again —
    the new run's results reflect it. **Reset to defaults** restores the values baked into
    `app/scheduling/domain.py`. Reopen an older run in Run history — it still shows the weights it
    actually used at the time, unaffected by the change.
11. Confirm employees can't reach any of this: no **Generate** section, no **Scheduling weights**
    nav link; `/admin/solver-weights` redirects away for an employee (or a manager — it's
    admin-only); `POST /api/v1/periods/{id}/schedule-runs`, `.../revert`, and
    `GET|PUT /api/v1/solver/weights` all return `403` for an employee token, and the weights
    endpoints return `403` for a manager token too.

Component tests:
`frontend/src/features/schedule/generate/{GeneratePanel,ConfirmGenerateDialog,RunDiagnostics}.test.tsx`
cover the generate flow's idle/running/success/failure states, the locked/discard confirmation, and
the translated diagnostics panel. Backend: `backend/tests/api/test_schedule_runs.py` covers the
revert endpoint end-to-end, and `backend/tests/scheduling/test_cpsat_golden.py` covers the
`unused_available` reasoning (already-assigned-same-day, contract-max-reached, and the
not-prioritized fallback when no hard rule excludes a candidate) as pure solver-output invariants.
