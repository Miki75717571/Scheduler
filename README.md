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
