from fastapi import FastAPI
from fastapi.responses import HTMLResponse


app = FastAPI()
tasks = []
task_id_counter = 0


@app.get("/tasks")
def get_tasks():
   return tasks


@app.post("/tasks")
def create_task(task: dict):
   global task_id_counter
  
   task["id"] = task_id_counter
   task_id_counter += 1
  
   tasks.append(task)
   return task




@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
   for i, t in enumerate(tasks):
       if t["id"] == task_id:
           return tasks.pop(i)
   return {"error": "Task not found"}


@app.get("/", response_class=HTMLResponse)
def home():
   return """
   <html>
   <body>
       <h1>Task Manager</h1>
      
       <input id="title" placeholder="Task title">
       <input id="priority" type="number" placeholder="Priority">
       <input id="duration" type="number" placeholder="Duration">
       <button onclick="addTask()">Add Task</button>
      
       <h2>Tasks</h2>
       <ul id="tasks"></ul>
      
       <script>
           const API = "/tasks";
          
           async function fetchTasks() {
               const res = await fetch(API);
               const data = await res.json();
              
               const list = document.getElementById("tasks");
               list.innerHTML = "";
              
               data.forEach(t => {
                   list.innerHTML += `
                       <li>
                           ${t.title}, (P:${t.priority}, ${t.duration} min)
                       </li>
                   `;
               });
           }
          
           async function addTask() {
               const title = document.getElementById("title").value;
               const priority = document.getElementById("priority").value;
               const duration = document.getElementById("duration").value;
              
               await fetch(API,{
                   method: "POST",
                   headers: {"Content-Type": "application/json"},
                   body: JSON.stringify ({ title, priority, duration})
               });
              
               fetchTasks();
           }
          
           fetchTasks();
       </script>
   </body>
   </html>
  
   """

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# 🔥 Static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 🔥 Templates folder
templates = Jinja2Templates(directory="templates")

# ======================
# MAIN PAGES
# ======================

@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse("homepage.html", {"request": request})

@app.get("/tasks", response_class=HTMLResponse)
def tasks(request: Request):
    return templates.TemplateResponse("tasks.html", {"request": request})

@app.get("/calendar", response_class=HTMLResponse)
def calendar(request: Request):
    return templates.TemplateResponse("calendar.html", {"request": request})

# ======================
# TASK ACTION PAGES
# ======================

@app.get("/add", response_class=HTMLResponse)
def add_task(request: Request):
    return templates.TemplateResponse("addtask.html", {"request": request})

@app.get("/edit", response_class=HTMLResponse)
def edit_task(request: Request):
    return templates.TemplateResponse("edittask.html", {"request": request})

@app.get("/delete", response_class=HTMLResponse)
def delete_task(request: Request):
    return templates.TemplateResponse("deletetask.html", {"request": request})

# ======================
# USER PAGES
# ======================

@app.get("/signup", response_class=HTMLResponse)
def signup(request: Request):
    return templates.TemplateResponse("newuser.html", {"request": request})

@app.get("/forgot", response_class=HTMLResponse)
def forgot_password(request: Request):
    return templates.TemplateResponse("forgotpassword.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("saveduser.html", {"request": request})

# ======================
# RUN
# ======================
# run with:
# uvicorn app:app --reload
