from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import pandas as pd
import time
import os
from sqlalchemy import func, text
from werkzeug.security import check_password_hash
import init_db
from init_db import User, Subscription, SubscriptionStatus, SessionLocal

app = Flask(__name__)

# Secret key for sessions (important for login sessions)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

# Allow frontend domain to talk to backend
app.config.update(
    SESSION_COOKIE_SAMESITE="None",   # allow cookie to be sent cross-site
    SESSION_COOKIE_SECURE=True        # required when SameSite=None (works only on HTTPS)
)
CORS(app, supports_credentials=True, origins=["https://xpresstenders.com"])

# -----------------------------
# Google Sheets CSV setup
# -----------------------------
CSV_URL = "https://docs.google.com/spreadsheets/d/1IcLsng5J0Iwl9bTTCyIWiLpVdyWpbCOmUxXmuaboBho/gviz/tq?tqx=out:csv"
df_cache = None
last_fetched = 0
CACHE_TIMEOUT = 120  # 2 minutes


def get_data():
    """Fetch tender data from Google Sheets with caching and safe fallbacks"""
    global df_cache, last_fetched
    now = time.time()
    if df_cache is None or (now - last_fetched) > CACHE_TIMEOUT:
        try:
            df = pd.read_csv(CSV_URL, dtype=str)  # keep everything as strings
            df = normalize_headers(df)
            df_cache = df
            last_fetched = now
        except Exception as e:
            app.logger.exception("Failed to read CSV from Google Sheets")
            # safe empty dataframe with expected headers so the app still runs
            df_cache = pd.DataFrame(columns=[
                "Items","Quantity Required","State","Department","Category",
                "Tender Value","Published Date","Closing Date","Status"
            ])
            last_fetched = now
    return df_cache

# -----------------------------
# Helper functions
# -----------------------------
def _lc(v):
    return str(v or "").strip().lower()

def _to_int(v):
    """Convert tender value safely (remove commas, handle blanks)"""
    try:
        return int(str(v or "0").replace(",", "").strip())
    except Exception:
        return 0

def parse_date(dstr):
    """Convert DD-MM-YYYY string from CSV into a date object"""
    try:
        return datetime.strptime(str(dstr).strip(), "%d-%m-%Y").date()
    except Exception:
        return None

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]  # strip weird spaces
    return df

def pick_col(df: pd.DataFrame, candidates) -> str | None:
    """
    Find the first matching column by exact (case-insensitive) name,
    then by substring containment as a fallback.
    """
    if df is None or df.empty:
        return None
    lookup = {c.strip().lower(): c for c in df.columns}
    # exact match first
    for name in candidates:
        key = str(name).strip().lower()
        if key in lookup:
            return lookup[key]
    # then 'contains' match
    for c_lower, orig in lookup.items():
        for name in candidates:
            if str(name).strip().lower() in c_lower:
                return orig
    return None

def unique_list(df: pd.DataFrame, col: str) -> list[str]:
    if not col or col not in df.columns:
        return []
    vals = (df[col].dropna().astype(str)
            .map(lambda x: x.strip())
            .replace({"-": ""}))
    return sorted([v for v in vals.unique().tolist() if v])

# -----------------------------
# Routes
# -----------------------------
@app.route("/ping")
def ping():
    return jsonify(ok=True, time=datetime.utcnow().isoformat())

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
    data = (request.get_json(silent=True) or {})
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")

    db = SessionLocal()
    user = db.query(User).filter(func.lower(User.email) == email).first()

    if not user:
        db.close()
        return jsonify({"success": False, "message": "User not found"}), 401

    if not check_password_hash(user.password_hash, password):
        db.close()
        return jsonify({"success": False, "message": "Wrong password"}), 401

    # success
    session["user_id"] = user.id

    sub = db.query(Subscription).filter_by(
        user_id=user.id, status=SubscriptionStatus.active
    ).first()
    db.close()

    subscription_status = "premium" if sub else "free"
    return jsonify({"success": True, "subscription": subscription_status})


@app.route("/logout")
def logout():
    """Clear session"""
    session.pop("user_id", None)
    return jsonify({"success": True, "message": "Logged out"})


@app.route("/filters")
def filters():
    try:
        df = get_data()

        # try multiple header variants that commonly appear
        dept_col = pick_col(df, ["Department", "Department Name", "Buyer Name",
                                 "Organisation", "Organisation Chain"])
        cat_col  = pick_col(df, ["Category", "Item Category", "Bid Type"])
        state_col= pick_col(df, ["State", "State/UT", "State Name", "Location"])

        data = {
            "departments": unique_list(df, dept_col),
            "categories":  unique_list(df, cat_col),
            "states":      unique_list(df, state_col),
        }
        return jsonify(data)
    except Exception as e:
        app.logger.exception("/filters failed")
        # never 500 to the browser; return empty arrays instead
        return jsonify({"departments": [], "categories": [], "states": []})


@app.route("/search")
def search():
    """Search tenders: always show results, but lock details if not premium"""

    user_id = session.get("user_id")
    subscription = None

    if user_id:
        db = SessionLocal()
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

    # 🔹 Apply filters
    department = request.args.get("department")
    category = request.args.get("category")
    state = request.args.get("state")
    min_value = request.args.get("minValue", type=int)
    max_value = request.args.get("maxValue", type=int)
    date = request.args.get("date")
    closing = request.args.get("closing")
    status = request.args.get("status")

    if department:
        results = [r for r in results if _lc(r.get("Department")) == _lc(department)]
    if category:
        results = [r for r in results if _lc(r.get("Category")) == _lc(category)]
    if state:
        results = [r for r in results if _lc(r.get("State")) == _lc(state)]
    if min_value is not None:
        results = [r for r in results if _to_int(r.get("Tender Value")) >= min_value]
    if max_value is not None:
        results = [r for r in results if _to_int(r.get("Tender Value")) <= max_value]
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()  # frontend ISO
            results = [r for r in results if parse_date(r.get("Published Date")) and parse_date(r.get("Published Date")) >= filter_date]
        except Exception:
            pass
    if closing:
        try:
            filter_closing = datetime.strptime(closing, "%Y-%m-%d").date()
            results = [r for r in results if parse_date(r.get("Closing Date")) and parse_date(r.get("Closing Date")) <= filter_closing]
        except Exception:
            pass
    if status:
        results = [r for r in results if _lc(r.get("Status")) == _lc(status)]

    # 🔹 Premium restriction
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
