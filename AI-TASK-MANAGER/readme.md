# AI-Based Task Manager Agent 

This repository contains an **Agentic AI System** designed to manage tasks through natural language. It interprets user intent using an LLM, maps it to structured actions, and maintains a persistent state with an audit trail in a PostgreSQL database.

**Walkthrough Video:** https://www.youtube.com/watch?v=EMUBNdEmMQ8

---

## Problem Understanding

Traditional task managers require manual entry into rigid forms. The goal of this project was to build an **intelligent interface** where a user can interact with their productivity data using natural prose.

The system must:

1. **Understand Intent:** Differentiate between adding, updating, viewing, or deleting.
2. **Extract Entities:** Identify dates, priorities, and titles from unstructured text.
3. **Ensure Reliability:** Guarantee that the LLM output is valid before performing database transactions.

---

## Solution Architecture

The system follows a **Modular Agentic Router** pattern. Instead of a linear script, the LLM acts as the "Decision Engine," and the database acts as the "Long-Term Memory."

### Components:

* **LLM Brain:** `qwen2.5-1.5b-instruct` (via LM Studio/OpenAI API) handles the transformation of natural language into JSON.
* **Validation Layer:** Uses **Pydantic** to enforce strict data types and schema integrity.
* **Persistence Layer:** **PostgreSQL** handles structured data and task relationships.
* **Memory System:** A `task_history` table tracks every state change, allowing the agent to "remember" previous modifications for a specific task.

---

## Key Parts of the Code

### 1. The Schema (`/models/llm_client.py`)

We use Pydantic classes to define the "contract" between the LLM and the Python backend. This ensures that the agent cannot execute an "update_task" action without a valid `task_id`.

### 2. The Agentic Router (`/src/app.py`)

The logic is decoupled. The `TaskAgent` only cares about interpretation, while the `DatabaseManager` only cares about execution. This separation of concerns makes the system **unit-testable**.

### 3. Smart History (`/utils/db_manager.py`)

The `log_history` function captures the `details` of every action in a JSONB format within Postgres. This enables future implementation of features like "Undo" or "Summarize my week's activity."

---

##  Best Practices Used

* **Modular Design:** Code is split into `/models`, `/utils`, and `/src` for maintainability.
* **Schema Validation:** Implemented Pydantic models to prevent LLM hallucinations from breaking the database.
* **Security:** Used SQLAlchemy's `text()` with parameter binding (`:user_id`) to prevent **SQL Injection**.
* **Environment Safety:** Configured for `.env` usage (secrets management).
* **Error Handling:** Try-except blocks wrap the LLM parsing and DB execution layers to provide user-friendly feedback in the UI.

---

##  Challenges & Solutions

| Challenge | Solution |
| --- | --- |
| **LLM JSON Inconsistency** | Small models like Qwen-1.5B can sometimes include prose or markdown in their response. I used a strict system prompt and a Pydantic validation wrapper to retry or catch parsing errors.

---

## Setup Instructions

### 1. Prerequisites

* Docker & Docker Compose (Recommended) OR Python 3.10+
* LM Studio running `qwen2.5-1.5b-instruct` (or an OpenAI API Key)

### 2. Manual Setup

1. **Clone the repo:**
```bash
git clone https://github.com/yourusername/ai-task-manager.git
cd ai-task-manager

```


2. **Install Dependencies:**
```bash
pip install -r requirements.txt

```


3. **Environment Variables:**
Create a `.env` file in the root:
```env
POSTGRES_URL=postgresql://user:password@localhost:5432/taskdb
OPENAI_API_BASE=http://your-ip:1234/v1

```


4. **Run Application:**
```bash
python -m streamlit run main.py


```
