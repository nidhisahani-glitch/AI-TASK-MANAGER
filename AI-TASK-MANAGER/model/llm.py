import json
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from typing import Optional, Literal

class TaskSchema(BaseModel):
    action: Literal["add_task", "list_tasks", "update_task", "delete_task", "view_task_history"]
    task_id: Optional[int] = None
    title: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[Literal["Low", "Medium", "High"]] = None
    due_date: Optional[str] = None
    status: Optional[Literal["Pending", "Completed"]] = None

class TaskAgent:
    def __init__(self, base_url: str, model_name: str):
        self.client = OpenAI(base_url=base_url, api_key="lm-studio")
        self.model = model_name
        self.system_prompt = "You are an AI task manager. Convert input to STRICT JSON. Actions: add_task, list_tasks, update_task, delete_task, view_task_history."

    def parse_input(self, user_input: str) -> TaskSchema:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0
        )
        content = response.choices[0].message.content
        # Extract JSON and validate with Pydantic
        data = json.loads(content)
        return TaskSchema(**data)