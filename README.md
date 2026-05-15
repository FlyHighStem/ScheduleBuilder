# ScheduleBuilder

ScheduleBuilder is a student planner app with a local AI assistant powered by Ollama.

## Features

- Save tasks locally in the browser for the test user
- Add, edit, delete, and clear tasks with pop-up menus
- Organize tasks by category: School, Work, and Personal
- Track urgency, importance, start time, and end time
- View tasks on a weekly schedule
- Ask the AI assistant to create, edit, move, or organize tasks

## Project Structure

- `main.py` - FastAPI app, page routes, and the AI endpoint
- `templates/` - HTML pages and shared navigation
- `static/app.js` - shared local storage and task helper functions
- `static/shared.css` - dashboard, modal, navbar, and shared styles
- `static/tasks.css` - task page styles
- `static/calendar.css` - full calendar styles
- `database/` - reserved spot for the future database integration

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Make sure Ollama is running and the model is installed:

```bash
ollama pull llama3.2:3b
```

Start the app:

```bash
uvicorn main:app --reload
```
