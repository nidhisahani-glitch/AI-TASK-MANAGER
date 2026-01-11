from sqlalchemy import create_engine, text
import json

class DatabaseManager:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)

    def log_history(self, task_id: int, action: str, details: dict):
        with self.engine.begin() as conn:
            conn.execute(
                text("INSERT INTO task_history (task_id, action, details) VALUES (:id, :act, :det)"),
                {"id": task_id, "act": action, "det": json.dumps(details)}
            )

    def add_task(self, task: dict, user_id: int):
        with self.engine.begin() as conn:
            result = conn.execute(
                text("INSERT INTO tasks (user_id, title, priority, due_date) VALUES (:u, :t, :p, :d) RETURNING id"),
                {"u": user_id, "t": task['title'], "p": task.get('priority', 'Medium'), "d": task.get('due_date')}
            )
            task_id = result.scalar()
        self.log_history(task_id, "CREATED", task)
        return task_id
    
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