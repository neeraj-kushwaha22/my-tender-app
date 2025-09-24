from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import pandas as pd
import time
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from werkzeug.security import check_password_hash
import init_db
from init_db import User, Subscription, SubscriptionStatus, SessionLocal

app = Flask(__name__)

# Secret key for sessions (important for login sessions)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Allow frontend domain to talk to backend
CORS(app, supports_credentials=True, origins=["https://xpresstenders.com"])

# -----------------------------
# Google Sheets CSV setup
# -----------------------------
CSV_URL = "https://docs.google.com/spreadsheets/d/1IcLsng5J0Iwl9bTTCyIWiLpVdyWpbCOmUxXmuaboBho/gviz/tq?tqx=out:csv"
df_cache = None
last_fetched = 0
CACHE_TIMEOUT = 120  # 2 minutes


def get_data():
    """Fetch tender data from Google Sheets with caching"""
    global df_cache, last_fetched
    now = time.time()
    if df_cache is None or (now - last_fetched) > CACHE_TIMEOUT:
        df_cache = pd.read_csv(CSV_URL)
        last_fetched = now
    return df_cache

# -----------------------------
# Routes
# -----------------------------

@app.route("/db-health")
def db_health():
    """Check DB connection"""
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT NOW();"))
        db.close()
        return jsonify(ok=True, db_time=str(result.scalar()))
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@app.route("/login", methods=["POST"])
def login():
    """Login and return subscription info"""
    data = request.get_json()  # <-- FIX: read JSON instead of form
    email = data.get("email")
    password = data.get("password")

    db = SessionLocal()
    user = db.query(User).filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        session["user_id"] = user.id

        # Check subscription
        sub = db.query(Subscription).filter_by(
            user_id=user.id,
            status=SubscriptionStatus.active
        ).first()
        db.close()

        subscription_status = "premium" if sub else "free"
        return jsonify({"success": True, "subscription": subscription_status})
    else:
        db.close()
        return jsonify({"success": False, "message": "Invalid credentials"}), 401


@app.route("/logout")
def logout():
    """Clear session"""
    session.pop("user_id", None)
    return jsonify({"success": True, "message": "Logged out"})


@app.route("/search")
def search():
    """Search tenders, restrict details if not premium"""
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Login required"}), 403

    db = SessionLocal()
    user_id = session["user_id"]
    subscription = db.query(Subscription).filter_by(
        user_id=user_id, status=SubscriptionStatus.active
    ).first()
    db.close()

    query = request.args.get("q", "").lower()
    df = get_data()

    if query:
        results = df[df.apply(
            lambda row: row.astype(str).str.lower().str.contains(query).any(),
            axis=1
        )]
    else:
        results = df

    results = results.to_dict(orient="records")

    # If not premium, restrict details
    if not subscription:
        locked_results = []
        for r in results:
            locked_results.append({
                "Items": r.get("Items", "N/A"),
                "Quantity Required": r.get("Quantity Required", "N/A"),
                "Note": "🔒 Upgrade to premium to see full tender details"
            })
        results = locked_results

    return jsonify({"success": True, "results": results})


if __name__ == "__main__":
    app.run(debug=True)
