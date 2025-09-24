import os
import sys
from dotenv import load_dotenv
load_dotenv()  # 👈 ensure .env is loaded before importing init_db

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from init_db import Base, User  # reuse models from init_db.py

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set. Please configure it in Render or .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def create_user(email: str, password: str):
    """Create a new user with given email & password"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            print(f"ℹ️ User {email} already exists.")
            return

        hashed = generate_password_hash(password)
        user = User(email=email, password_hash=hashed)
        db.add(user)
        db.commit()
        print(f"✅ User {email} created successfully.")
    except Exception as e:
        print("❌ Error:", e)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python manage_users.py <email> <password>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    create_user(email, password)
