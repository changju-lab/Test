const STORAGE_KEY = "daily-todos";

const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const countEl = document.getElementById("todo-count");
const dateEl = document.getElementById("today-date");

let allTodos = loadAllTodos();
let currentDateKey = getTodayKey();
let todos = getTodosForDate(currentDateKey);

function getTodayKey() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDate(dateKey) {
  const [year, month, day] = dateKey.split("-");
  return `${year}년 ${Number(month)}월 ${Number(day)}일`;
}

function updateTodayDate() {
  const todayKey = getTodayKey();

  if (todayKey !== currentDateKey) {
    saveTodos();
    currentDateKey = todayKey;
    todos = getTodosForDate(currentDateKey);
  }

  dateEl.textContent = formatDate(currentDateKey);
}

function loadAllTodos() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    if (!data) return {};

    const parsed = JSON.parse(data);

    if (Array.isArray(parsed)) {
      const migrated = { [getTodayKey()]: parsed };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
      return migrated;
    }

    return parsed;
  } catch {
    return {};
  }
}

function getTodosForDate(dateKey) {
  if (!allTodos[dateKey]) {
    allTodos[dateKey] = [];
  }
  return allTodos[dateKey];
}

function saveTodos() {
  allTodos[currentDateKey] = todos;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(allTodos));
}

function updateCount() {
  const remaining = todos.filter((todo) => !todo.done).length;
  const total = todos.length;

  if (total === 0) {
    countEl.textContent = "";
    return;
  }

  countEl.textContent = `남은 할 일 ${remaining}개 / 전체 ${total}개`;
}

function renderTodos() {
  updateTodayDate();
  list.innerHTML = "";

  if (todos.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-message";
    empty.textContent = "할 일이 없습니다. 새로운 할 일을 추가해 보세요.";
    list.appendChild(empty);
    updateCount();
    return;
  }

  todos.forEach((todo) => {
    const item = document.createElement("li");
    item.className = "todo-item";
    item.dataset.id = todo.id;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "todo-checkbox";
    checkbox.checked = todo.done;
    checkbox.addEventListener("change", () => toggleTodo(todo.id));

    const text = document.createElement("span");
    text.className = "todo-text" + (todo.done ? " done" : "");
    text.textContent = todo.text;

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-btn";
    deleteBtn.textContent = "삭제";
    deleteBtn.addEventListener("click", () => deleteTodo(todo.id));

    item.append(checkbox, text, deleteBtn);
    list.appendChild(item);
  });

  updateCount();
}

function addTodo(text) {
  updateTodayDate();

  const trimmed = text.trim();
  if (!trimmed) return;

  todos.push({
    id: crypto.randomUUID(),
    text: trimmed,
    date: currentDateKey,
    done: false,
  });

  saveTodos();
  renderTodos();
}

function toggleTodo(id) {
  const todo = todos.find((item) => item.id === id);
  if (!todo) return;

  todo.done = !todo.done;
  saveTodos();
  renderTodos();
}

function deleteTodo(id) {
  todos = todos.filter((item) => item.id !== id);
  allTodos[currentDateKey] = todos;
  saveTodos();
  renderTodos();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  addTodo(input.value);
  input.value = "";
  input.focus();
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    renderTodos();
  }
});

setInterval(updateTodayDate, 60000);

renderTodos();
