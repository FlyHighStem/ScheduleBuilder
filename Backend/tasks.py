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
