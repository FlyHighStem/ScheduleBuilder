const STORAGE_PREFIX = "schedulebuilder";
const DEFAULT_TEST_USER = {
  fullname: "Test User",
  name: "Test User",
  email: "test@test.com",
  password: "test123",
  theme: "dark",
  reminders: true
};
const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
let tasksCache = [];
let taskDatabaseQueue = Promise.resolve();

function readJson(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function getUsers() {
  const users = readJson(`${STORAGE_PREFIX}.users`, {});
  if (!users[DEFAULT_TEST_USER.email]) {
    users[DEFAULT_TEST_USER.email] = DEFAULT_TEST_USER;
    writeJson(`${STORAGE_PREFIX}.users`, users);
  }
  return users;
}

function saveUser(user) {
  const users = getUsers();
  const fullUser = {
    ...users[user.email],
    ...user,
    name: user.fullname || user.name || users[user.email]?.name || "Test User"
  };
  users[fullUser.email] = fullUser;
  writeJson(`${STORAGE_PREFIX}.users`, users);
  localStorage.setItem(`${STORAGE_PREFIX}.currentUser`, fullUser.email);
  return fullUser;
}

function getCurrentUser() {
  const users = getUsers();
  const currentEmail = localStorage.getItem(`${STORAGE_PREFIX}.currentUser`) || DEFAULT_TEST_USER.email;
  localStorage.setItem(`${STORAGE_PREFIX}.currentUser`, currentEmail);
  return users[currentEmail] || saveUser(DEFAULT_TEST_USER);
}

function applyTheme(theme = "dark") {
  document.body.classList.toggle("light-theme", theme === "light");
}

function getTaskApiUrl(path = "") {
  const userEmail = encodeURIComponent(getCurrentUser().email);
  return `/api/tasks${path}?user_email=${userEmail}`;
}

async function syncTasksFromDatabase() {
  try {
    const response = await fetch(getTaskApiUrl());
    if (!response.ok) return;
    const tasks = await response.json();
    saveTasks(tasks);
    document.dispatchEvent(new CustomEvent("tasksSynced"));
  } catch (error) {
    console.warn("Task database sync failed", error);
  }
}

function notifyTasksChanged() {
  document.dispatchEvent(new CustomEvent("tasksChanged"));
}

async function saveTaskToDatabase(task) {
  const response = await fetch(getTaskApiUrl(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(task)
  });
  if (!response.ok) throw new Error("Task database save failed");
  return response.json();
}

async function deleteTaskFromDatabase(taskId) {
  const response = await fetch(getTaskApiUrl(`/${encodeURIComponent(taskId)}`), { method: "DELETE" });
  if (!response.ok) throw new Error("Task database delete failed");
  return response.json();
}

async function clearTasksFromDatabase() {
  const response = await fetch(getTaskApiUrl(), { method: "DELETE" });
  if (!response.ok) throw new Error("Task database clear failed");
  return response.json();
}

function queueTaskDatabaseWrite(operation) {
  taskDatabaseQueue = taskDatabaseQueue
    .then(operation)
    .catch((error) => console.warn(error.message || "Task database write failed", error));
  return taskDatabaseQueue;
}

function waitForTaskDatabaseWrites() {
  return taskDatabaseQueue;
}

function getTasks() {
  return tasksCache;
}

function saveTasks(tasks) {
  tasksCache = Array.isArray(tasks) ? tasks : [];
  notifyTasksChanged();
}

function normalizeHour(value, fallback) {
  const hour = Number(value);
  if (!Number.isFinite(hour)) return fallback;
  return Math.min(23, Math.max(0, hour));
}

function normalizeTaskTiming(task) {
  const startHour = normalizeHour(task.startHour ?? task.hour, 9);
  const rawEndHour = task.endHour ?? (startHour + Number(task.time || 1));
  const endHour = Math.max(startHour + 1, normalizeHour(rawEndHour, startHour + 1));

  return {
    ...task,
    hour: startHour,
    startHour,
    endHour: Math.min(24, endHour)
  };
}

function formatScheduleHour(hour) {
  const suffix = hour >= 12 ? "PM" : "AM";
  const h = hour % 12 === 0 ? 12 : hour % 12;
  return `${h} ${suffix}`;
}

function formatDateValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getNextSevenDays() {
  const today = new Date();
  const days = [];

  for (let i = 0; i < 7; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() + i);

    days.push({
      offset: i,
      value: formatDateValue(date),
      weekday: date.toLocaleDateString("en-US", { weekday: "short" }),
      date: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      label: i === 0
        ? `Today, ${date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`
        : date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
    });
  }

  return days;
}

function getCurrentWeekDays(baseDate = new Date()) {
  const start = new Date(baseDate);
  start.setHours(12, 0, 0, 0);
  start.setDate(baseDate.getDate() - baseDate.getDay());

  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);

    return {
      offset: index,
      value: formatDateValue(date),
      weekday: date.toLocaleDateString("en-US", { weekday: "short" }),
      date: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      label: date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
    };
  });
}

function fillDayDropdown(select, selectedOffset = 0) {
  if (!select) return;
  select.innerHTML = "";
  getNextSevenDays().forEach((day) => {
    const option = document.createElement("option");
    option.value = day.offset;
    option.dataset.date = day.value;
    option.textContent = day.label;
    select.appendChild(option);
  });
  select.value = String(selectedOffset);
}

function getTodayValue() {
  return formatDateValue(new Date());
}

function getDayOffsetFromDate(dateValue) {
  if (!dateValue) return 0;
  const today = new Date(`${getTodayValue()}T12:00:00`);
  const date = new Date(`${dateValue}T12:00:00`);
  const diff = Math.round((date - today) / 86400000);
  return Math.max(0, diff);
}

function dateFromValue(dateValue) {
  return new Date(`${dateValue}T12:00:00`);
}

function getWeekdayKey(dateValue) {
  return WEEKDAY_KEYS[dateFromValue(dateValue).getDay()];
}

function taskOccursOnDate(task, dateValue) {
  if (task.due === dateValue) return true;

  const repeatDays = Array.isArray(task.repeatDays) ? task.repeatDays : [];
  if (!repeatDays.length) return false;
  if (!repeatDays.includes(getWeekdayKey(dateValue))) return false;

  if (!task.due) return true;
  return dateFromValue(dateValue) >= dateFromValue(task.due);
}

function timesOverlap(firstTask, secondTask) {
  const first = normalizeTaskTiming(firstTask);
  const second = normalizeTaskTiming(secondTask);
  return first.startHour < second.endHour && second.startHour < first.endHour;
}

function findHighImportanceConflict(candidate, excludeTaskId = "") {
  if (!candidate?.due) return null;
  const candidateDates = getCandidateOccurrenceDates(candidate);
  return getTasks().find((task) => {
    if (task.id === excludeTaskId) return false;
    return candidateDates.some((dateValue) => taskOccursOnDate(task, dateValue) && timesOverlap(candidate, task));
  }) || null;
}

function getHighImportanceConflictMessage(candidate, conflict) {
  return `${candidate.name || candidate.title || "That task"} overlaps with ${conflict.name || conflict.title}. Events cannot overlap. Pick a different open time.`;
}

function getCandidateOccurrenceDates(candidate) {
  if (!candidate?.due) return [];
  const dates = new Set([candidate.due]);
  const repeatDays = Array.isArray(candidate.repeatDays) ? candidate.repeatDays : [];
  if (repeatDays.length) {
    const startDate = dateFromValue(candidate.due);
    for (let offset = 0; offset < 30; offset++) {
      const date = new Date(startDate);
      date.setDate(startDate.getDate() + offset);
      const dateValue = formatDateValue(date);
      if (taskOccursOnDate(candidate, dateValue)) {
        dates.add(dateValue);
      }
    }
  }
  return Array.from(dates);
}

function getTaskTimeLabel(task) {
  const normalized = normalizeTaskTiming(task);
  return `${formatScheduleHour(normalized.startHour)}-${formatScheduleHour(normalized.endHour)}`;
}

function createTask(task) {
  const tasks = getTasks();
  const startHour = Number(task.startHour ?? task.hour ?? 9);
  const newTask = normalizeTaskTiming({
    id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    name: task.name,
    title: task.name,
    description: task.description || "",
    category: task.category || "school",
    urgency: task.urgency || "none",
    importance: task.importance || "medium",
    repeatDays: Array.isArray(task.repeatDays) ? task.repeatDays : [],
    due: task.due || "",
    time: task.time || "",
    dayOffset: Number(task.dayOffset || 0),
    hour: startHour,
    startHour,
    endHour: Number(task.endHour ?? (startHour + Number(task.time || 1))),
    createdAt: new Date().toISOString()
  });
  tasks.push(newTask);
  saveTasks(tasks);
  queueTaskDatabaseWrite(() => saveTaskToDatabase(newTask));
  return newTask;
}

function updateTask(taskId, updates) {
  const tasks = getTasks().map((task) => {
    if (task.id !== taskId) return task;
    const name = updates.name || updates.title || task.name;
    return normalizeTaskTiming({ ...task, ...updates, name, title: name });
  });
  saveTasks(tasks);
  const updatedTask = tasks.find((task) => task.id === taskId);
  if (updatedTask) {
    queueTaskDatabaseWrite(() => saveTaskToDatabase(updatedTask));
  }
}

function deleteSavedTask(taskId) {
  saveTasks(getTasks().filter((task) => task.id !== taskId));
  queueTaskDatabaseWrite(() => deleteTaskFromDatabase(taskId));
}

function clearTasks() {
  saveTasks([]);
  queueTaskDatabaseWrite(clearTasksFromDatabase);
}

function showMessage(element, text, isError = false) {
  if (!element) return;
  element.textContent = text;
  element.classList.toggle("is-error", isError);
  element.hidden = false;
}

function openDialog(dialog) {
  if (dialog && !dialog.open) dialog.showModal();
}

function closeDialog(dialog) {
  if (dialog && dialog.open) dialog.close();
}

function setupNavbarMenus() {
  const user = getCurrentUser();
  const userButton = document.querySelector("[data-user-menu-button]");
  const profileForm = document.getElementById("profileForm");
  const settingsForm = document.getElementById("settingsForm");

  if (userButton) {
    const suffix = userButton.classList.contains("user-menu-btn") ? " ☰" : " ▾";
    userButton.textContent = `${user.fullname || user.name || "User"}${suffix}`;
  }

  applyTheme(user.theme || "dark");
  syncTasksFromDatabase();

  document.querySelectorAll("[data-open-dialog]").forEach((button) => {
    button.addEventListener("click", () => openDialog(document.getElementById(button.dataset.openDialog)));
  });

  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => closeDialog(button.closest("dialog")));
  });

  if (profileForm) {
    profileForm.fullname.value = user.fullname || user.name || "";
    profileForm.email.value = user.email || "";
    profileForm.addEventListener("submit", (event) => {
      event.preventDefault();
      saveUser({
        ...getCurrentUser(),
        fullname: profileForm.fullname.value.trim() || "Test User",
        email: profileForm.email.value.trim() || DEFAULT_TEST_USER.email
      });
      location.reload();
    });
  }

  if (settingsForm) {
    settingsForm.theme.value = user.theme || "dark";
    settingsForm.reminders.checked = user.reminders !== false;
    settingsForm.addEventListener("submit", (event) => {
      event.preventDefault();
      saveUser({
        ...getCurrentUser(),
        theme: settingsForm.theme.value,
        reminders: settingsForm.reminders.checked
      });
      applyTheme(settingsForm.theme.value);
      closeDialog(settingsForm.closest("dialog"));
    });
  }

  const logoutButton = document.querySelector("[data-logout]");
  if (logoutButton) {
    logoutButton.addEventListener("click", () => {
      localStorage.setItem(`${STORAGE_PREFIX}.currentUser`, DEFAULT_TEST_USER.email);
      window.location.href = "/";
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(getCurrentUser().theme || "dark");
  setupNavbarMenus();
});
