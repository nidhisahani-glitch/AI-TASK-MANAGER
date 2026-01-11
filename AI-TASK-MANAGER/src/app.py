import json
from openai import OpenAI
from sqlalchemy import create_engine, text

# =========================
# CONFIG
# =========================

LM_STUDIO_BASE_URL = "http://192.168.1.34:1234/v1"
MODEL_NAME = "qwen2.5-1.5b-instruct"

POSTGRES_URL = "postgresql://postgres:12032003@localhost:3000/agent"
# ⚠️ change username, password, db name

# =========================
# CLIENTS
# =========================

client = OpenAI(
    base_url=LM_STUDIO_BASE_URL,
    api_key="lm-studio"
)

engine = create_engine(POSTGRES_URL)

# =========================
# SYSTEM PROMPT
# =========================

SYSTEM_PROMPT = """
You are an AI task management agent.

Convert user input into STRICT JSON.
NO explanations. NO markdown. ONLY JSON.

Allowed actions:
- add_task
- list_tasks
- update_task
- delete_task
- view_task_history

JSON format for add_task:
{
  "action": "add_task",
  "title": "string",
  "category": "string or null",
  "priority": "Low | Medium | High",
  "due_date": "YYYY-MM-DD or null"
}

JSON format for list_tasks:
{
  "action": "list_tasks"
}

JSON format for update_task:
{
  "action": "update_task",
  "task_id": number,
  "title": "string or null",
  "category": "string or null",
  "priority": "Low | Medium | High or null",
  "due_date": "YYYY-MM-DD or null",
  "status": "Pending | Completed or null"
}

JSON format for delete_task:
{
  "action": "delete_task",
  "task_id": number
}

JSON format for view_task_history:
{
  "action": "view_task_history",
  "task_id": number
}
"""

# =========================
# LLM PARSER
# =========================

def parse_user_input(user_input: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]
    )

    content = response.choices[0].message.content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON from LLM:\n{content}")

# =========================
# MEMORY LOGGER
# =========================

def log_history(task_id: int, action: str, details: dict):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO task_history (task_id, action, details)
                VALUES (:task_id, :action, :details)
            """),
            {
                "task_id": task_id,
                "action": action,
                "details": json.dumps(details)
            }
        )

# =========================
# TASK OPERATIONS
# =========================

def add_task(task: dict):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO tasks (title, category, priority, due_date)
                VALUES (:title, :category, :priority, :due_date)
                RETURNING id
            """),
            {
                "title": task["title"],
                "category": task.get("category"),
                "priority": task.get("priority", "Medium"),
                "due_date": task.get("due_date")
            }
        )
        task_id = result.scalar()

    log_history(task_id, "CREATED", task)
    print(f"✅ Task added (ID: {task_id})")

def list_tasks():
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT id, title, priority, status, due_date
                FROM tasks
                ORDER BY created_at DESC
            """)
        ).fetchall()

    if not rows:
        print("📭 No tasks found.")
        return

    print("\n📋 Tasks:")
    for r in rows:
        print(
            f"- [{r.id}] {r.title} | "
            f"Priority: {r.priority} | "
            f"Status: {r.status} | "
            f"Due: {r.due_date}"
        )

def update_task(task: dict):
    task_id = task["task_id"]

    fields = []
    values = {}
    changes = {}

    for field in ["title", "category", "priority", "due_date", "status"]:
        if task.get(field) is not None:
            fields.append(f"{field} = :{field}")
            values[field] = task[field]
            changes[field] = task[field]

    if not fields:
        print("⚠️ No fields to update.")
        return

    values["id"] = task_id

    query = f"""
        UPDATE tasks
        SET {", ".join(fields)}
        WHERE id = :id
    """

    with engine.begin() as conn:
        result = conn.execute(text(query), values)

    if result.rowcount == 0:
        print("❌ Task not found.")
        return

    log_history(task_id, "UPDATED", changes)
    print("✅ Task updated.")

def delete_task(task: dict):
    task_id = task["task_id"]

    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM tasks WHERE id = :id"),
            {"id": task_id}
        )

    if result.rowcount == 0:
        print("❌ Task not found.")
        return

    log_history(task_id, "DELETED", {})
    print("🗑️ Task deleted.")

def view_task_history(task: dict):
    task_id = task["task_id"]

    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT action, details, created_at
                FROM task_history
                WHERE task_id = :task_id
                ORDER BY created_at ASC
            """),
            {"task_id": task_id}
        ).fetchall()

    if not rows:
        print("📭 No history found.")
        return

    print(f"\n🧠 History for Task {task_id}:")
    for r in rows:
        print(f"- [{r.created_at}] {r.action} → {r.details}")

# =========================
# AGENT LOOP
# =========================

def run_agent():
    print("🤖 AI Task Manager Agent")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("🧑 You: ")

        if user_input.lower() == "exit":
            break

        try:
            parsed = parse_user_input(user_input)
            action = parsed.get("action")

            if action == "add_task":
                add_task(parsed)
            elif action == "list_tasks":
                list_tasks()
            elif action == "update_task":
                update_task(parsed)
            elif action == "delete_task":
                delete_task(parsed)
            elif action == "view_task_history":
                view_task_history(parsed)
            else:
                print("⚠️ Unknown action.")

        except Exception as e:
            print("❌ Error:", e)

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    run_agent()
