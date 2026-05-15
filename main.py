import os
import json
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

from database.repositories import TaskRepository, UserRepository, initialize_database

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI()
ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
initialize_database()
task_repository = TaskRepository()
user_repository = UserRepository()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

test_user = {
    "id": 1,
    "name": "test test",
    "email": "test@test.com"
}


class AIRequest(BaseModel):
    message: str
    tasks: list[dict] = []


@app.get("/api/tasks")
def get_tasks_api(user_email: str = "test@test.com"):
    return task_repository.list_for_user(user_email)


@app.post("/api/tasks")
def create_task(task: dict, user_email: str = "test@test.com"):
    return task_repository.upsert(user_email, task)


@app.put("/api/tasks/{task_id}")
def update_task_api(task_id: str, task: dict, user_email: str = "test@test.com"):
    task["id"] = task_id
    return task_repository.upsert(user_email, task)


@app.delete("/api/tasks/{task_id}")
def delete_task_api(task_id: str, user_email: str = "test@test.com"):
    task_repository.delete(user_email, task_id)
    return {"deleted": task_id}


@app.delete("/api/tasks")
def clear_tasks_api(user_email: str = "test@test.com"):
    task_repository.clear(user_email)
    return {"cleared": True}


@app.post("/api/ai-schedule")
def ai_schedule(request: AIRequest):
    current_tasks = json.dumps(request.tasks, indent=2)
    prompt = f"""
You are an AI schedule assistant for a student planner app.

Help the user organize:
- tasks
- deadlines
- classes
- work shifts
- study blocks
- breaks

Make the schedule realistic, clear, and easy to follow.

The user's current saved tasks are JSON below. Use task ids when editing, moving, or deleting existing tasks.
{current_tasks}

You can update the user's local tasks by returning actions.
Allowed actions:
- create_task with a task object
- update_task with task_id and updates object
- delete_task with task_id

Task fields:
- name: short title
- category: school, work, or personal
- description: useful details
- urgency: none, low, medium, or high
- importance: low, medium, or high
- due: YYYY-MM-DD if known, otherwise empty string
- time: estimated hours as a string if known
- dayOffset: 0 for today through 6 for six days from now
- startHour: 0 through 23
- endHour: 1 through 24 and always after startHour
- repeatDays: optional list using mon, tue, wed, thu, fri, sat, sun

High-importance task rule:
- If a task has importance "high", do not update_task, delete_task, or move it unless the user's latest request clearly gives permission to change that specific high-importance task.
- If a high-importance task blocks the schedule and permission is not clear, explain the conflict in reply and ask the user what to do before changing it.

Return ONLY valid JSON in this exact shape:
{{
  "reply": "friendly chat response explaining what you did or recommend",
  "actions": [
    {{
      "type": "create_task",
      "task": {{"name": "Example", "category": "school", "description": "", "urgency": "medium", "importance": "medium", "due": "", "time": "", "dayOffset": 0, "startHour": 9, "endHour": 10, "repeatDays": []}}
    }}
  ]
}}

If no task changes are needed, return an empty actions array.

User request:
{request.message}
"""

    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    api_request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(api_request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8")
        raise HTTPException(
            status_code=500,
            detail=f"Ollama request failed: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise HTTPException(
            status_code=500,
            detail="Could not connect to Ollama. Make sure the Ollama app is open and llama3.2:3b is installed."
        ) from error

    try:
        ai_payload = json.loads(data["response"])
        reply = ai_payload.get("reply", "")
        actions = ai_payload.get("actions", [])
    except (KeyError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=500,
            detail="Ollama responded, but the app could not read the answer."
        ) from error

    return {"reply": reply, "actions": actions}


@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="homepage.html",
        context={"request": request}
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "user": test_user
        }
    )


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={"request": request, "user": test_user}
    )


@app.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={"request": request, "user": test_user}
    )


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="newuser.html",
        context={"request": request}
    )


@app.get("/forgot", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="forgotpassword.html",
        context={"request": request}
    )


@app.get("/login")
def login_page():
    return RedirectResponse(url="/dashboard")
