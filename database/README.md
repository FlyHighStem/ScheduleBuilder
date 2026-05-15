# Database Integration Placeholder

This folder is reserved for the future database work.

The app currently saves test-user tasks in browser `localStorage` through `static/app.js`. When the real database is added, this folder is the intended place for:

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

Keep the API surface in `main.py` small so the frontend can switch from local storage to backend database calls without rewriting the whole UI.
