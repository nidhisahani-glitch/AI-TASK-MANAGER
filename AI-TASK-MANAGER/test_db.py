from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:12032003@localhost:3000/agent"
)

with engine.connect() as conn:
    print("✅ Connected to PostgreSQL!")
