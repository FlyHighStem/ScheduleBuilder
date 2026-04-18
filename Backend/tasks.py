from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.responses import HTMLResponse

import models
from database import SessionLocal, engine, Base

app = FastAPI()
tasks = []
task_id_counter = 0



def get_db():
    db = SessionLocal()
    try:
      yield db
    finally:
       db.close()



@app.get("/tasks")
def get_tasks(db: Session = Depends(get_db)):
   return db.query(models.Task).all()


@app.post("/tasks")
def create_task(task: dict, db: Session = Depends(get_db)):
    new_task = models.Task(
       
       title=task["title"],
       priority=task["priority"],
       duration=task["duration"]
       
    )
    
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

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
