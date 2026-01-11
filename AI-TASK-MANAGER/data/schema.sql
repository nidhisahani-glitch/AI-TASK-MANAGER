CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT,
    priority TEXT,
    due_date DATE,
    status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE task_history (
    id SERIAL PRIMARY KEY,
    task_id INTEGER,
    action TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

--------------------------------------------------------------------------------

--Create users table 
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL  
);
ALTER TABLE tasks 
ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

INSERT INTO users (username, password) 
VALUES ('admin', 'admin') 
ON CONFLICT (username) DO NOTHING;