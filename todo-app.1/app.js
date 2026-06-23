const STORAGE_KEY = "daily-todos-v1";

const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const countEl = document.getElementById("todo-count");
const dateDisplay = document.getElementById("date-display");

let todos = [];

function getTodayString() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatDateDisplay(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  return `${y}년 ${m}월 ${d}일 (${weekdays[date.getDay()]})`;
}

function loadStorage() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : { lastDate: null, todos: [] };
  } catch {
    return { lastDate: null, todos: [] };
  }
}

function saveStorage() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ lastDate: getTodayString(), todos })
  );
}

function processDateChange() {
  const today = getTodayString();
  const stored = loadStorage();
  let dateChanged = false;

  if (stored.lastDate && stored.lastDate !== today) {
    dateChanged = true;
    stored.todos = stored.todos
      .filter((todo) => todo.repeat)
      .map((todo) => ({ ...todo, done: false }));
  }

  todos = stored.todos;
  saveStorage();
  dateDisplay.textContent = formatDateDisplay(today);
  return dateChanged;
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

    const repeatLabel = document.createElement("label");
    repeatLabel.className = "repeat-toggle" + (todo.repeat ? " active" : "");
    repeatLabel.title = "매일 자동으로 다시 나타납니다";

    const repeatCheckbox = document.createElement("input");
    repeatCheckbox.type = "checkbox";
    repeatCheckbox.className = "repeat-checkbox";
    repeatCheckbox.checked = todo.repeat;
    repeatCheckbox.addEventListener("change", () => toggleRepeat(todo.id));

    const repeatText = document.createElement("span");
    repeatText.textContent = "반복";

    repeatLabel.append(repeatCheckbox, repeatText);

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-btn";
    deleteBtn.textContent = "삭제";
    deleteBtn.addEventListener("click", () => deleteTodo(todo.id));

    item.append(checkbox, text, repeatLabel, deleteBtn);
    list.appendChild(item);
  });

  updateCount();
}

function addTodo(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  todos.push({
    id: crypto.randomUUID(),
    text: trimmed,
    done: false,
    repeat: false,
    date: getTodayString(),
  });

  saveStorage();
  renderTodos();
}

function toggleTodo(id) {
  const todo = todos.find((item) => item.id === id);
  if (!todo) return;

  todo.done = !todo.done;
  saveStorage();
  renderTodos();
}

function deleteTodo(id) {
  todos = todos.filter((item) => item.id !== id);
  saveStorage();
  renderTodos();
}

function toggleRepeat(id) {
  const todo = todos.find((item) => item.id === id);
  if (!todo) return;

  todo.repeat = !todo.repeat;
  saveStorage();
  renderTodos();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  addTodo(input.value);
  input.value = "";
  input.focus();
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && processDateChange()) {
    renderTodos();
  }
});

processDateChange();
renderTodos();
