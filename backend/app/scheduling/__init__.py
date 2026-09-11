"""Pure scheduling domain and solver.

No sqlalchemy, app.models, or app.db imports allowed anywhere under this
package - see tests/scheduling/test_purity.py, which enforces it. Everything
here operates on plain data (frozen dataclasses in `domain.py`) so the solver
can be unit-tested, replayed, and swapped without touching the app.
"""
