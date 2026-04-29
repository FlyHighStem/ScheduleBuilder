from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# 1. Setup Static and Templates
# Ensure your 'static' and 'templates' folders are in the same directory as this file
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 2. Data Storage
# Renamed from 'tasks' to 'tasks_db' to avoid conflict with the 'tasks' route function
tasks_db = []
task_id_counter = 0

# ======================
# API ENDPOINTS (The Logic)
# ======================

@app.get("/api/tasks")
def get_tasks_api():
    return tasks_db

@app.post("/api/tasks")
def create_task(task: dict):
    global task_id_counter
    task["id"] = task_id_counter
    task_id_counter += 1
    tasks_db.append(task)
    return task

@app.delete("/api/tasks/{task_id}")
def delete_task_api(task_id: int):
    global tasks_db
    for i, t in enumerate(tasks_db):
        if t["id"] == task_id:
            return tasks_db.pop(i)
    return {"error": "Task not found"}

# ======================
# PAGE ROUTES
# ======================

@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse(
        request=request, name="homepage.html", context={"request": request}
    )

@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="tasks.html", context={"request": request}
    )

@app.get("/calendar", response_class=HTMLResponse)
def calendar_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="calendar.html", context={"request": request}
    )

@app.get("/add", response_class=HTMLResponse)
def add_task_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="addtask.html", context={"request": request}
    )

@app.get("/edit", response_class=HTMLResponse)
def edit_task_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="edittask.html", context={"request": request}
    )

@app.get("/delete", response_class=HTMLResponse)
def delete_task_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="deletetask.html", context={"request": request}
    )

@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="newuser.html", context={"request": request}
    )

@app.get("/forgot", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="forgotpassword.html", context={"request": request}
    )

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    # If this is a page to show after login, use this.
    # If it's a POST action for the form, you'll need an @app.post route.
    return templates.TemplateResponse(
        request=request, name="saveduser.html", context={"request": request}
    )

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    # If this is a page to show after login, use this.
    # If it's a POST action for the form, you'll need an @app.post route.
    return templates.TemplateResponse(
        request=request, name="profile.html", context={"request": request}
    )

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    # If this is a page to show after login, use this.
    # If it's a POST action for the form, you'll need an @app.post route.
    return templates.TemplateResponse(
        request=request, name="settings.html", context={"request": request}
    )