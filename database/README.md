# Database Layer

This folder is the local database layer for ScheduleBuilder.

The test-user schedule data is stored in the project SQLite file at `schedulebuilder.db` through the FastAPI routes in `main.py`. Browser storage is only used for lightweight login/session-style UI state such as the current test user and theme.

When the team adds the future shared database, this folder is the intended place for:

- database connection setup
- table/model definitions
- user queries
- task queries
- migration or seed scripts

Suggested future files:

- `connection.py`
- `models.py`
- `task_repository.py`
- `user_repository.py`

Keep the API surface in `main.py` small so the frontend can switch from local SQLite to the shared backend without rewriting the whole UI.
