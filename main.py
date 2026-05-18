import os
import json
import re
import uuid
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
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


WEEKDAY_ALIASES = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "wednesday": 2,
    "wedensday": 2,
    "wedensay": 2,
    "wednsday": 2,
    "wensday": 2,
    "wendsday": 2,
    "weds": 2,
    "wed": 2,
    "thursday": 3,
    "thurday": 3,
    "thrusday": 3,
    "thurs": 3,
    "thur": 3,
    "thu": 3,
    "friday": 4,
    "fridy": 4,
    "fri": 4,
    "saturday": 5,
    "saterday": 5,
    "sat": 5,
    "sunday": 6,
    "sundy": 6,
    "sun": 6,
}
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

WEEKDAY_PATTERN = "|".join(re.escape(day) for day in sorted(WEEKDAY_ALIASES, key=len, reverse=True))
TODAY_WORDS = ["today", "2day", "tdy"]
TOMORROW_WORDS = ["tomorrow", "tmrw", "tmr", "tomorow", "tommorow", "tom"]
TASK_WORDS = [
    "add", "create", "schedule", "sched", "remind", "reminder", "put", "make a task", "new task",
    "test", "exam", "final", "finals", "quiz", "homework", "hw", "project", "assignment",
    "assigment", "assignement", "class", "lecture", "lab", "practice", "shift",
    "appointment", "appt", "meeting", "meet", "event", "plans", "plan", "dinner", "lunch",
    "hangout", "hang out", "game"
]


def message_wants_task(message):
    lowered = message.lower()
    if any(word in lowered for word in TASK_WORDS):
        return True
    return bool(re.search(r"\b(?:i have|ive got|i've got|i got)\s+(?:a\s+)?date\b", lowered))


def message_mentions_importance(message):
    lowered = message.lower()
    return bool(re.search(r"\bimportance\s*(?:is|=|:)?\s*[1-5]\b", lowered)) or any(
        phrase in lowered for phrase in ["very important", "high importance", "not important", "low importance", "medium importance", "important"]
    )


def date_to_day_offset(target_date):
    return max(0, (target_date - date.today()).days)


def task_time_range(task):
    start_hour = int(task.get("startHour", task.get("hour", 9)) or 9)
    end_hour = int(task.get("endHour", start_hour + 1) or start_hour + 1)
    return start_hour, end_hour


def ranges_overlap(first_start, first_end, second_start, second_end):
    return first_start < second_end and second_start < first_end


def task_occurs_on_date(task, date_value):
    if task.get("due") == date_value:
        return True

    repeat_days = task.get("repeatDays") if isinstance(task.get("repeatDays"), list) else []
    if not repeat_days:
        return False

    target_date = date.fromisoformat(date_value)
    if WEEKDAY_KEYS[target_date.weekday()] not in repeat_days:
        return False

    if not task.get("due"):
        return True
    return target_date >= date.fromisoformat(task["due"])


def candidate_occurrence_dates(candidate, day_count=30):
    if not candidate.get("due"):
        return []

    start_date = date.fromisoformat(candidate["due"])
    dates = {candidate["due"]}
    repeat_days = candidate.get("repeatDays") if isinstance(candidate.get("repeatDays"), list) else []
    if repeat_days:
        for offset in range(day_count):
            current_date = start_date + timedelta(days=offset)
            date_value = current_date.isoformat()
            if task_occurs_on_date(candidate, date_value):
                dates.add(date_value)

    return sorted(dates)


def high_importance_conflict(candidate, tasks):
    candidate_dates = candidate_occurrence_dates(candidate)
    if not candidate_dates:
        return None

    candidate_start, candidate_end = task_time_range(candidate)
    candidate_id = str(candidate.get("id", ""))

    for task in tasks:
        if str(task.get("id", "")) == candidate_id:
            continue
        for candidate_date in candidate_dates:
            if not task_occurs_on_date(task, candidate_date):
                continue
            task_start, task_end = task_time_range(task)
            if ranges_overlap(candidate_start, candidate_end, task_start, task_end):
                return task

    return None


def high_importance_conflict_reply(candidate, conflict):
    return (
        f"I cannot schedule {candidate.get('name', 'that task')} at {candidate.get('startHour') % 12 or 12}"
        f"{'PM' if candidate.get('startHour', 0) >= 12 else 'AM'} because it overlaps with "
        f"{conflict.get('name', 'task')} from {task_time_range(conflict)[0] % 12 or 12}"
        f"{'PM' if task_time_range(conflict)[0] >= 12 else 'AM'} to {task_time_range(conflict)[1] % 12 or 12}"
        f"{'PM' if task_time_range(conflict)[1] >= 12 else 'AM'}. Events cannot overlap. High-importance tasks also cannot be deleted."
    )


def format_hour_label(hour):
    suffix = "PM" if hour >= 12 else "AM"
    display_hour = hour % 12 or 12
    return f"{display_hour}{suffix}"


def message_asks_schedule(message):
    lowered = message.lower()
    return bool(
        re.search(r"\bwhat(?:'s| is)?\s+(?:on\s+)?(?:my\s+)?schedule\b", lowered)
        or re.search(r"\bwhat\s+do\s+i\s+have\b", lowered)
        or re.search(r"\banything\s+(?:today|tomorrow|tmrw|this week)\b", lowered)
        or re.search(r"\b(?:show|list|tell me)\s+(?:my\s+)?schedule\b", lowered)
        or re.search(r"\bnext\s+(?:event|task|class|thing)\b", lowered)
    )


def task_occurrences(tasks, start_date, day_count):
    occurrences = []
    for offset in range(day_count):
        current_date = start_date + timedelta(days=offset)
        date_value = current_date.isoformat()
        for task in tasks:
            if not task_occurs_on_date(task, date_value):
                continue
            start_hour, end_hour = task_time_range(task)
            occurrences.append({
                "task": task,
                "date": current_date,
                "date_value": date_value,
                "start_hour": start_hour,
                "end_hour": end_hour,
            })
    return sorted(occurrences, key=lambda item: (item["date"], item["start_hour"], item["end_hour"]))


def build_schedule_summary_response(request):
    today = date.today()
    lowered = request.message.lower()
    if any(word in lowered for word in TOMORROW_WORDS):
        start_date = today + timedelta(days=1)
        day_count = 1
        label = "tomorrow"
    elif "week" in lowered:
        start_date = today
        day_count = 7
        label = "this week"
    else:
        start_date = today
        day_count = 1
        label = "today"

    items = task_occurrences(request.tasks, start_date, day_count)
    if not items:
        return {
            "reply": f"You do not have anything scheduled {label}.",
            "actions": [],
        }

    lines = []
    for item in items[:8]:
        task = item["task"]
        date_label = item["date"].strftime("%a, %b %-d") if os.name != "nt" else item["date"].strftime("%a, %b %#d")
        lines.append(
            f"- {date_label}: {task.get('name', task.get('title', 'Task'))} "
            f"from {format_hour_label(item['start_hour'])} to {format_hour_label(item['end_hour'])}"
        )

    extra = "" if len(items) <= 8 else f"\n\nThere are {len(items) - 8} more items after that."
    return {
        "reply": f"Here is what is scheduled {label}:\n" + "\n".join(lines) + extra,
        "actions": [],
    }


def parse_schedule_date(message):
    lowered = message.lower()
    today = date.today()

    if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in TOMORROW_WORDS):
        return today + timedelta(days=1)
    if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in TODAY_WORDS):
        return today
    if re.search(r"\b(?:next|nxt)\s+week\b", lowered):
        return today + timedelta(days=7)

    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", lowered)
    if iso_match:
        return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    slash_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?\b", lowered)
    if slash_match:
        year = int(slash_match.group(3) or today.year)
        return date(year, int(slash_match.group(1)), int(slash_match.group(2)))

    for word, weekday in WEEKDAY_ALIASES.items():
        next_weekday = re.search(rf"\b(?:next|nxt)\s+{word}\b", lowered)
        if next_weekday or re.search(rf"\b{word}\b", lowered):
            days_ahead = (weekday - today.weekday()) % 7
            if days_ahead == 0 or next_weekday:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    return today


def parse_schedule_time(message):
    lowered = message.lower()
    range_match = re.search(
        r"\b(?:from\s+)?(\d{1,2})(?::\d{2})?\s*(am|pm)?\s*(?:-|to|until)\s*(\d{1,2})(?::\d{2})?\s*(am|pm)?\b",
        lowered,
    )
    if range_match:
        start_hour = int(range_match.group(1))
        end_hour = int(range_match.group(3))
        start_suffix = range_match.group(2) or range_match.group(4)
        end_suffix = range_match.group(4) or start_suffix
        start_hour = apply_time_suffix(start_hour, start_suffix)
        end_hour = apply_time_suffix(end_hour, end_suffix)
        if end_hour <= start_hour:
            end_hour += 12 if end_hour + 12 <= 24 else 1
        return max(0, min(23, start_hour)), max(1, min(24, end_hour))

    single_match = re.search(r"\b(?:at|around)?\s*(\d{1,2})(?::\d{2})?\s*(am|pm)\b", lowered)
    if single_match:
        start_hour = apply_time_suffix(int(single_match.group(1)), single_match.group(2))
        return max(0, min(23, start_hour)), max(1, min(24, start_hour + 1))

    return None, None


def apply_time_suffix(hour, suffix):
    if suffix == "pm" and hour != 12:
        return hour + 12
    if suffix == "am" and hour == 12:
        return 0
    return hour


def next_available_hour(tasks, target_date):
    busy_ranges = []
    date_value = target_date.isoformat()
    for task in tasks:
        if task.get("due") != date_value:
            continue
        start_hour = int(task.get("startHour", task.get("hour", 9)) or 9)
        end_hour = int(task.get("endHour", start_hour + 1) or start_hour + 1)
        busy_ranges.append((start_hour, end_hour))

    for hour in range(8, 21):
        if all(hour + 1 <= start or hour >= end for start, end in busy_ranges):
            return hour
    return 20


def detect_category(message):
    lowered = message.lower()
    if any(word in lowered for word in ["work", "shift", "job"]):
        return "work"
    if any(word in lowered for word in ["gym", "doctor", "family", "personal", "chores", "date", "appointment", "appt", "dinner", "lunch", "hangout", "hang out", "plans"]):
        return "personal"
    return "school"


def detect_priority(message, field):
    lowered = message.lower()
    number_match = re.search(r"\bimportance\s*(?:is|=|:)?\s*([1-5])\b", lowered)
    if number_match and field == "importance":
        return importance_level_from_number(int(number_match.group(1)))
    if "very important" in lowered or "high importance" in lowered or "important" in lowered:
        return "high"
    if "not important" in lowered or "low importance" in lowered:
        return "low"
    if field == "urgency" and any(word in lowered for word in ["urgent", "asap", "tonight", "due soon"]):
        return "high"
    return "medium" if field == "importance" else "none"


def importance_level_from_number(value):
    if value <= 2:
        return "low"
    if value <= 4:
        return "medium"
    return "high"


def clean_task_name(message):
    cleaned = re.sub(
        r"\b(i have|ive got|i've got|i got|to go to|go to|add|create|schedule|sched|make|put|remind me to|reminder|task|assignment|assigment|assignement|event|for|on|at|from|until|to|today|2day|tdy|tomorrow|tmrw|tmr|tomorow|tommorow|tom|next week|nxt week)\b",
        " ",
        message,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(rf"\b(?:next\s+)?(?:{WEEKDAY_PATTERN})\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:-|to|until)?\s*\d{0,2}(?::\d{2})?\s*(?:am|pm)?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}(?:/20\d{2})?)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned[:80].strip() or "New Task"
    return cleaned[0].upper() + cleaned[1:] if cleaned else "New Task"


def build_rule_based_schedule_response(request):
    message = request.message.strip()
    wants_task = message_wants_task(message)

    if not wants_task:
        return {
            "reply": "I can help plan that. Tell me the task, date, and time you want, and I can add it to your schedule.",
            "actions": [],
        }

    target_date = parse_schedule_date(message)
    start_hour, end_hour = parse_schedule_time(message)
    if start_hour is None:
        start_hour = next_available_hour(request.tasks, target_date)
        end_hour = start_hour + 1

    task_name = clean_task_name(message)
    task = {
        "id": str(uuid.uuid4()),
        "name": task_name,
        "title": task_name,
        "description": "",
        "category": detect_category(message),
        "urgency": detect_priority(message, "urgency"),
        "importance": detect_priority(message, "importance"),
        "due": target_date.isoformat(),
        "dayOffset": date_to_day_offset(target_date),
        "startHour": start_hour,
        "endHour": end_hour,
        "repeatDays": [],
    }
    conflict = high_importance_conflict(task, request.tasks)
    if conflict:
        return {
            "reply": high_importance_conflict_reply(task, conflict),
            "actions": [],
            "blocked_by_high_importance": True,
        }

    readable_date = target_date.strftime("%A, %b %-d") if os.name != "nt" else target_date.strftime("%A, %b %#d")
    return {
        "reply": f"I added {task_name} for {readable_date} from {start_hour % 12 or 12}{'PM' if start_hour >= 12 else 'AM'} to {end_hour % 12 or 12}{'PM' if end_hour >= 12 else 'AM'}.",
        "actions": [{"type": "create_task", "task": task}],
    }


def build_importance_question_response(request):
    scheduled = build_rule_based_schedule_response(request)
    if not scheduled["actions"]:
        return scheduled

    task = scheduled["actions"][0]["task"]
    return {
        "reply": (
            f"I can add {task['name']} for {task['due']} from "
            f"{task['startHour'] % 12 or 12}{'PM' if task['startHour'] >= 12 else 'AM'} to "
            f"{task['endHour'] % 12 or 12}{'PM' if task['endHour'] >= 12 else 'AM'}. "
            "How important is it from 1-5? 1 is low, 3 is normal, and 5 is high/protected."
        ),
        "actions": [],
        "pending_task": task,
        "needs_importance": True,
    }


def normalize_ai_actions(actions, request):
    normalized_actions = []
    blocked_reply = ""
    fallback = build_rule_based_schedule_response(request)
    fallback_task = fallback["actions"][0]["task"] if fallback["actions"] else None

    for action in actions or []:
        if action.get("type") != "create_task" or not isinstance(action.get("task"), dict):
            normalized_actions.append(action)
            continue

        task = {**action["task"]}
        if fallback_task:
            task.setdefault("id", str(uuid.uuid4()))
            task["due"] = fallback_task["due"]
            task["dayOffset"] = fallback_task["dayOffset"]
            task["startHour"] = fallback_task["startHour"]
            task["endHour"] = fallback_task["endHour"]
            task.setdefault("category", fallback_task["category"])
            task.setdefault("urgency", fallback_task["urgency"])
            task.setdefault("importance", fallback_task["importance"])
        if not task.get("due"):
            target_date = date.today()
            task["due"] = target_date.isoformat()
            task["dayOffset"] = 0
        task.setdefault("startHour", next_available_hour(request.tasks, date.fromisoformat(task["due"])))
        task.setdefault("endHour", int(task["startHour"]) + 1)
        task.setdefault("repeatDays", [])
        task.setdefault("category", "school")
        task.setdefault("urgency", "none")
        task.setdefault("importance", "medium")
        task["name"] = task.get("name") or task.get("title") or clean_task_name(request.message)
        task["title"] = task["name"]
        conflict = high_importance_conflict(task, request.tasks)
        if conflict:
            blocked_reply = high_importance_conflict_reply(task, conflict)
            continue
        normalized_actions.append({**action, "task": task})

    if fallback["actions"] and not any(action.get("type") == "create_task" for action in normalized_actions):
        return fallback["actions"], blocked_reply

    return normalized_actions, blocked_reply


@app.get("/api/tasks")
def get_tasks_api(user_email: str = "test@test.com"):
    return task_repository.list_for_user(user_email)


@app.post("/api/tasks")
def create_task(task: dict, user_email: str = "test@test.com"):
    conflict = high_importance_conflict(task, task_repository.list_for_user(user_email))
    if conflict:
        raise HTTPException(status_code=409, detail=high_importance_conflict_reply(task, conflict))
    return task_repository.upsert(user_email, task)


@app.put("/api/tasks/{task_id}")
def update_task_api(task_id: str, task: dict, user_email: str = "test@test.com"):
    task["id"] = task_id
    conflict = high_importance_conflict(task, task_repository.list_for_user(user_email))
    if conflict:
        raise HTTPException(status_code=409, detail=high_importance_conflict_reply(task, conflict))
    return task_repository.upsert(user_email, task)


@app.delete("/api/tasks/{task_id}")
def delete_task_api(task_id: str, user_email: str = "test@test.com"):
    existing_tasks = task_repository.list_for_user(user_email)
    task = next((saved_task for saved_task in existing_tasks if saved_task.get("id") == task_id), None)
    if task and task.get("importance") == "high":
        raise HTTPException(status_code=409, detail=f"{task.get('name', 'This task')} is high importance and cannot be deleted.")
    task_repository.delete(user_email, task_id)
    return {"deleted": task_id}


@app.delete("/api/tasks")
def clear_tasks_api(user_email: str = "test@test.com"):
    if any(task.get("importance") == "high" for task in task_repository.list_for_user(user_email)):
        raise HTTPException(status_code=409, detail="High-importance tasks cannot be deleted. Remove or lower those tasks before clearing the schedule.")
    task_repository.clear(user_email)
    return {"cleared": True}


@app.post("/api/ai-schedule")
def ai_schedule(request: AIRequest):
    if message_asks_schedule(request.message):
        return build_schedule_summary_response(request)

    if message_wants_task(request.message) and not message_mentions_importance(request.message):
        return build_importance_question_response(request)

    current_tasks = json.dumps(request.tasks, indent=2)
    today_value = date.today().isoformat()
    prompt = f"""
You are an AI schedule assistant for a student planner app.

Your job is to help the user plan, organize, and make decisions about events. You can:
- tell the user what is already scheduled
- explain what is coming up today or this week
- suggest better places in the week for tasks
- move tasks to better open spots when it is safe
- add new events and study blocks after collecting enough details

Help the user organize:
- tasks
- deadlines
- classes
- work shifts
- study blocks
- breaks

Make the schedule realistic, clear, and easy to follow.
Today's date is {today_value}. If the user asks to add or schedule a task and does not give a date, put it on today. If they do not give a time, choose an open one-hour block between 8 AM and 9 PM.

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

Schedule conflict rule:
- Never create, move, or update any event so it overlaps another event, no matter the importance.
- If a requested time overlaps another event, explain the conflict and suggest a different open time.

High-importance task rule:
- Never delete a high-importance task.
- Do not move or edit a high-importance task unless the user clearly asks to change that specific task.

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
        fallback = build_rule_based_schedule_response(request)
        fallback["reply"] += f" I used the built-in scheduler because the AI model request failed."
        return fallback
    except urllib.error.URLError as error:
        fallback = build_rule_based_schedule_response(request)
        fallback["reply"] += " I used the built-in scheduler because Ollama is not connected right now."
        return fallback

    try:
        ai_payload = json.loads(data["response"])
        reply = ai_payload.get("reply", "")
        actions, blocked_reply = normalize_ai_actions(ai_payload.get("actions", []), request)
        if blocked_reply:
            reply = blocked_reply if not actions else f"{reply}\n\n{blocked_reply}"
    except (KeyError, json.JSONDecodeError) as error:
        fallback = build_rule_based_schedule_response(request)
        fallback["reply"] += " I used the built-in scheduler because the AI response was not readable."
        return fallback

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
