# CLAUDE.md — Cafeteria Shift Scheduler

Authoritative design doc: `ARCHITECTURE.md`. This file records how we actually build it day to day. If the two conflict, `ARCHITECTURE.md` wins.

## What this is

A shift-scheduling app for a ~15–25 person cafeteria: employees submit monthly availability, a CP-SAT solver generates a fair, legal, well-staffed schedule, a manager reviews/fixes/publishes it. See `ARCHITECTURE.md` §1 for the three-part split (data collection / constraint solver / manager override surface) — that split is the core architectural invariant of this project.

## Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript (`strict: true`) |
| UI | Tailwind CSS + shadcn/ui |
| Data fetching | TanStack Query |
| Forms | react-hook-form + zod |
| i18n | react-i18next — `pl` (default) + `en` |
| Frontend tests | Vitest, Playwright |
| Frontend package manager | npm |
| Backend | Python 3.12 + FastAPI (async) |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic (sync — Alembic itself doesn't run async) |
| Validation | Pydantic v2 |
| Auth | JWT access token (short-lived, in memory) + refresh token (httpOnly cookie), argon2 password hashing |
| Solver | Google OR-Tools CP-SAT |
| Database | SQLite in dev (zero setup, `backend/.dev/db.sqlite3`), Postgres 16 in production (Supabase Session pooler when deployed there — see README) |
| Email | Resend (default; swappable — see `.env.example`) |
| Backend tests | pytest + pytest-asyncio, against SQLite |
| Backend package manager | uv |

## Folder layout

```
Scheduler/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            config, security, deps, i18n message keys
│   │   ├── db/               session, base, migrations/ (alembic)
│   │   ├── models/            SQLAlchemy models
│   │   ├── schemas/           Pydantic DTOs
│   │   ├── repositories/      all DB access, permission-aware (filter by acting user)
│   │   ├── services/          use cases (period_service, availability_service, …)
│   │   ├── rules/             rule definitions, availability_validator, schedule_validator
│   │   ├── scheduling/        ← PURE. See "Hard rule" below.
│   │   │   ├── domain.py      frozen dataclasses: SolverInput, SolverOutput
│   │   │   ├── cpsat.py       the CP-SAT model
│   │   │   ├── weights.py
│   │   │   └── explain.py     human-readable diagnostics
│   │   └── api/v1/            routers
│   └── tests/
│       ├── unit/
│       ├── scheduling/        golden fixture tests ← highest-value tests in the repo
│       └── api/
├── frontend/
│   └── src/{api,components,features,hooks,i18n,pages,lib}
├── docker-compose.yml
├── start.ps1                  ← one-command dev startup (PowerShell)
├── ARCHITECTURE.md
├── CLAUDE.md
└── README.md
```

## Hard rule: `backend/app/scheduling/` is pure

Nothing under `backend/app/scheduling/` may import `sqlalchemy`, `app.models`, or `app.db` — no session, no I/O, no ORM. Its only entry point is `solve(input: SolverInput) -> SolverOutput`, where `SolverInput`/`SolverOutput` are frozen dataclasses of plain values. This is enforced by a CI-run test that scans the module's imports and fails on violation. Do not weaken or skip that test to unblock a feature — fix the layering instead.

## Coding conventions

- **Python**: type hints on every function signature. `ruff` for linting + formatting, `mypy` for type checking. Both run clean before a phase is considered done.
- **TypeScript**: `strict: true`. `eslint` + `prettier`, clean before a phase is done.
- **Tables**: `PascalCase` in SQL/model docs (`ShiftSlot`, `AvailabilitySubmission`), matching `ARCHITECTURE.md` §3.
- **Dates/times**: shifts store a local `date` + local `time`, never a UTC timestamp (venue is `Europe/Warsaw`; DST must never shift a shift). Convert to a timestamp only at iCal export time.
- **Rules as data**: rule logic lives in `Rule` rows (`type` + JSON `params`), not as scattered `if` statements. New rule types get a handler registered in `app/rules/`, not inline conditionals in services or routers.
- **Scores**: never `UPDATE` an `EmployeeScore` in place — insert a new row with `effective_from` so past schedules stay explainable.
- **Authorization**: enforced in two independent layers — a route-level `require_role` dependency, and repository methods that filter rows by the acting user. Never rely on hiding UI elements. Every manager-only endpoint needs an API test asserting an employee token gets 403 or filtered results.
- **i18n**: no user-visible string hardcoded in a component — always a translation key in `frontend/src/i18n/{pl,en}.json`. Backend errors return a message key + params, never an English sentence, so the frontend translates. `pl` and `en` must have identical key sets (checked in CI). Code, comments, identifiers, and commit messages stay in English regardless.
- **Commits**: small, focused, clear English messages.
- **Secrets**: never committed. Every env var documented in `.env.example`. In development, missing secrets auto-generate and cache in `backend/.dev/secrets.json` (gitignored) — see `backend/app/core/config.py`. This is dev-only: `APP_ENV=production` requires every secret set explicitly and refuses to start otherwise (`tests/unit/test_config.py` asserts this).
- **Database portability**: every model must work unchanged on both SQLite (dev) and Postgres (prod). No `postgresql.ENUM`/`postgresql.UUID`/`JSONB`/`server_default=func.gen_random_uuid()` or other Postgres-only constructs. Use `sqlalchemy.Uuid(as_uuid=True)` with a Python-side `default=uuid.uuid4`, `app.db.types.StrEnumType` + a `CheckConstraint` for enum-like columns (not a native `Enum` type), `app.db.types.UTCDateTime` for any timestamp that gets compared (SQLite silently drops tz-awareness on read, which breaks naive `<`/`>` comparisons), and the portable `sqlalchemy.JSON` type if/when a JSON column is needed. Every migration must declare its constraints inline inside `create_table()`, not via a separate `ALTER TABLE`-based op call afterward (SQLite can't do most of those outside Alembic's batch mode).

## Commands

Filled in as each phase lands; keep this section current.

**Run everything (dev, zero setup — no Docker, no DB server, no `.env`):**
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

**Run everything (Docker, optional):**
```
docker compose up backend frontend         # Postgres/Supabase via DATABASE_URL, or sqlite default
docker compose --profile local-db up       # + a local Postgres container
```

**Backend (from `backend/`):**
```
uv run pytest                  # tests
uv run pytest tests/scheduling # solver golden tests only
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy .                  # type check
uv run alembic upgrade head    # apply migrations
uv run alembic revision --autogenerate -m "..."  # new migration
uv run python -m app.seed      # seed demo data
```

**Frontend (from `frontend/`):**
```
npm run dev                    # dev server
npm run test                   # Vitest
npm run test:e2e               # Playwright
npm run lint                   # eslint
npm run format                 # prettier
npm run typecheck              # tsc --noEmit
```

## Testing priorities (in order)

1. Solver invariants (golden fixtures — assert invariants, not exact rosters; `random_seed` set, `num_search_workers=1`)
2. Authorization boundaries (role/ownership filtering, every manager endpoint vs. an employee token)
3. Rule validators (availability-phase and schedule-phase)
4. API contracts
5. UI

Write tests as you go, not at the end.

## Build order

Phase 0 (scaffold) → 1 (auth/invites/roles) → 2 (availability collection) → 3 (manual scheduling + publish) → 4 (scoring) → 5 (solver) → 6 (polish). Full contents per phase: `ARCHITECTURE.md` §8. Stop after each phase for review: migrations written, tests passing, `README.md` updated, plus a short note on what to click through to verify it.
