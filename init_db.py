import os
from dotenv import load_dotenv
load_dotenv()  # 👈 ensure .env is loaded before DATABASE_URL

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import enum
from werkzeug.security import generate_password_hash

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL is not set. Please configure it in Render or .env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ---------- MODELS ----------
class SubscriptionStatus(enum.Enum):
    active = "active"
    expired = "expired"
    canceled = "canceled"
    pending = "pending"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(191), unique=True, nullable=False)
    password_hash = Column(String(191), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    price_inr = Column(Integer, nullable=False, default=0)
    duration_days = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.pending)
    start_at = Column(DateTime(timezone=True))
    end_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ---------- INIT FUNCTION ----------
def init_db():
    Base.metadata.create_all(engine)  # create tables if missing
    db = SessionLocal()

    # Seed plans
    plans = [
        {"code": "FREE", "name": "Free Plan", "price_inr": 0, "duration_days": 0},
        {"code": "PREMIUM_MONTH", "name": "Premium Monthly", "price_inr": 499, "duration_days": 30},
        {"code": "PREMIUM_YEAR", "name": "Premium Yearly", "price_inr": 2999, "duration_days": 365},
    ]
    for p in plans:
        existing_plan = db.query(Plan).filter_by(code=p["code"]).first()
        if not existing_plan:
            db.add(Plan(**p))
            print(f"✅ Plan {p['code']} created")
        else:
            print(f"ℹ️ Plan {p['code']} already exists")

    # Ensure admin user exists
    admin_email = "admin@xpresstenders.com"
    existing_admin = db.query(User).filter_by(email=admin_email).first()
    if not existing_admin:
        admin_user = User(
            email=admin_email,
            password_hash=generate_password_hash("Admin@123")
        )
        db.add(admin_user)
        print(f"✅ Admin user {admin_email} created with default password 'Admin@123'")
    else:
        print(f"ℹ️ Admin user {admin_email} already exists")

    db.commit()
    db.close()
    print("🎉 Database initialization complete.")

if __name__ == "__main__":
    init_db()
