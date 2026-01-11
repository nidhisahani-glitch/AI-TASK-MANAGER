import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from openai import OpenAI
import json
import datetime

# =========================
# CONFIG
# =========================

LM_STUDIO_BASE_URL = "http://192.168.1.34:1234/v1"
MODEL_NAME = "qwen2.5-1.5b-instruct"

POSTGRES_URL = "postgresql://postgres:12032003@localhost:3000/agent"
# ⚠️ For deployment, change to your cloud PostgreSQL URL and store in Streamlit secrets

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
# AUTHENTICATION
# =========================

def authenticate(username: str, password: str) -> int | None:
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT id FROM users
                WHERE username = :username AND password = :password
            """),
            {"username": username, "password": password}  # Plain text for demo; use hashing in production
        )
        user = result.fetchone()
        return user[0] if user else None

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

def add_task(task: dict, user_id: int) -> str:
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO tasks (user_id, title, category, priority, due_date)
                VALUES (:user_id, :title, :category, :priority, :due_date)
                RETURNING id
            """),
            {
                "user_id": user_id,
                "title": task["title"],
                "category": task.get("category"),
                "priority": task.get("priority", "Medium"),
                "due_date": task.get("due_date")
            }
        )
        task_id = result.scalar()

    log_history(task_id, "CREATED", task)
    return f"✅ Task added (ID: {task_id})"

def list_tasks(user_id: int) -> str:
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT id, title, priority, status, due_date
                FROM tasks
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """),
            {"user_id": user_id}
        ).fetchall()

    if not rows:
        return "📭 No tasks found."

    output = "\n📋 Tasks:\n"
    for r in rows:
        output += (
            f"- [{r.id}] {r.title} | "
            f"Priority: {r.priority} | "
            f"Status: {r.status} | "
            f"Due: {r.due_date}\n"
        )
    return output

def update_task(task: dict, user_id: int) -> str:
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
        return "⚠️ No fields to update."

    values["id"] = task_id
    values["user_id"] = user_id

    query = f"""
        UPDATE tasks
        SET {", ".join(fields)}
        WHERE id = :id AND user_id = :user_id
    """

    with engine.begin() as conn:
        result = conn.execute(text(query), values)

    if result.rowcount == 0:
        return "❌ Task not found or not owned by you."

    log_history(task_id, "UPDATED", changes)
    return "✅ Task updated."

def delete_task(task: dict, user_id: int) -> str:
    task_id = task["task_id"]

    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM tasks WHERE id = :id AND user_id = :user_id"),
            {"id": task_id, "user_id": user_id}
        )

    if result.rowcount == 0:
        return "❌ Task not found or not owned by you."

    log_history(task_id, "DELETED", {})
    return "🗑️ Task deleted."

def view_task_history(task: dict, user_id: int) -> str:
    task_id = task["task_id"]

    # Check ownership
    with engine.begin() as conn:
        owns = conn.execute(
            text("SELECT 1 FROM tasks WHERE id = :id AND user_id = :user_id"),
            {"id": task_id, "user_id": user_id}
        ).scalar()

    if not owns:
        return "❌ Task not found or not owned by you."

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
        return "📭 No history found."

    output = f"\n🧠 History for Task {task_id}:\n"
    for r in rows:
        output += f"- [{r.created_at}] {r.action} → {r.details}\n"
    return output

# =========================
# HANDLE ACTION
# =========================

def handle_action(parsed: dict, user_id: int) -> str:
    action = parsed.get("action")

    if action == "add_task":
        return add_task(parsed, user_id)
    elif action == "list_tasks":
        return list_tasks(user_id)
    elif action == "update_task":
        return update_task(parsed, user_id)
    elif action == "delete_task":
        return delete_task(parsed, user_id)
    elif action == "view_task_history":
        return view_task_history(parsed, user_id)
    else:
        return "⚠️ Unknown action."

# =========================
# STREAMLIT UI
# =========================

st.set_page_config(page_title="AI Task Manager", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for better UI theme (dark mode inspired)
st.markdown("""
    <style>
    .stApp {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    .stTextInput > div > div > input {
        background-color: #2d2d2d;
        color: #ffffff;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
    }
    .stDataFrame {
        background-color: #2d2d2d;
    }
    .stSelectbox > div > div > div {
        background-color: #2d2d2d;
        color: #ffffff;
    }
    .stTextArea > div > div > textarea {
        background-color: #2d2d2d;
        color: #ffffff;
    }
    .stChatMessage {
        background-color: #2d2d2d;
    }
    </style>
""", unsafe_allow_html=True)

st.sidebar.title("🤖 AI Task Manager")
st.sidebar.markdown("""
This is a **chat-based AI task manager**.

You can:
- Add tasks
- List tasks
- Update tasks
- Delete tasks
- View task history
""")

if "user_id" not in st.session_state:
    st.header("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user_id = authenticate(username, password)
        if user_id:
            st.session_state.user_id = user_id
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password.")
else:
    tabs = st.tabs([
        "🤖 Chatbot",
        "📋 View Tasks",
        "🧠 Task History",
        "🧪 SQL Playground"
    ])

    user_id = st.session_state.user_id

    # =========================
    # TAB 1: CHATBOT
    # =========================
    with tabs[0]:
        st.header("🤖 Chat with Task Manager")

        if "chat" not in st.session_state:
            st.session_state.chat = []

        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["content"])

        user_input = st.chat_input("Type your task command...")

        if user_input:
            st.session_state.chat.append({"role": "user", "content": user_input})
            st.chat_message("user").write(user_input)

            try:
                parsed = parse_user_input(user_input)
                response = handle_action(parsed, user_id)
            except Exception as e:
                response = f"❌ Error: {str(e)}"

            st.session_state.chat.append({"role": "assistant", "content": response})
            st.chat_message("assistant").write(response)

            st.rerun()  # Real-time update

    # =========================
    # TAB 2: VIEW TASKS
    # =========================
    with tabs[1]:
        st.header("📋 All Tasks")

        if st.button("Refresh Tasks"):
            st.rerun()

        query = """
            SELECT * FROM tasks 
            WHERE user_id = :user_id 
            ORDER BY created_at DESC
        """
        df = pd.read_sql(text(query), engine, params={"user_id": user_id})

        st.dataframe(df, width="stretch")

    # =========================
    # TAB 3: TASK HISTORY
    # =========================
    with tabs[2]:
        st.header("🧠 Task History")

        if st.button("Refresh History"):
            st.rerun()

        task_ids_query = """
            SELECT id FROM tasks 
            WHERE user_id = :user_id
        """
        task_ids = pd.read_sql(text(task_ids_query), engine, params={"user_id": user_id})["id"].tolist()

        if task_ids:
            task_id = st.selectbox("Select Task ID", task_ids)

            history_query = """
                SELECT action, details, created_at
                FROM task_history
                WHERE task_id = :task_id
                ORDER BY created_at
            """

            history_df = pd.read_sql(
                text(history_query),
                engine,
                params={"task_id": task_id}
            )

            st.dataframe(history_df, width="stretch")
        else:
            st.info("No tasks found.")

    # =========================
    # TAB 4: SQL PLAYGROUND
    # =========================
    with tabs[3]:
        st.header("🧪 SQL Playground")

        st.warning("⚠️ Only run SELECT queries if you are unsure. Restricted to your data.")

        sql = st.text_area(
            "Write your SQL query:",
            height=150,
            placeholder="SELECT * FROM tasks WHERE user_id = YOUR_USER_ID;"
        )

        if st.button("Run Query"):
            try:
                # For security, could add user_id filter, but for demo, allow
                result = pd.read_sql(sql, engine)
                st.success("Query executed successfully!")
                st.dataframe(result, width="stretch")
            except Exception as e:
                st.error(str(e))

