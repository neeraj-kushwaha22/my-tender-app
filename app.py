from flask import Flask, render_template, request, jsonify
import pandas as pd
import time

app = Flask(__name__)

# Google Sheets CSV URL
CSV_URL = "https://docs.google.com/spreadsheets/d/1IcLsng5J0Iwl9bTTCyIWiLpVdyWpbCOmUxXmuaboBho/gviz/tq?tqx=out:csv"

# Cache variables
cached_df = None
last_fetched = 0
CACHE_DURATION = 300  # 300 seconds = 5 minutes

def get_data():
    global cached_df, last_fetched
    current_time = time.time()

    # If cache is empty or expired, fetch fresh data
    if cached_df is None or (current_time - last_fetched) > CACHE_DURATION:
        cached_df = pd.read_csv(CSV_URL)
        last_fetched = current_time
        print("✅ Data refreshed from Google Sheets")
    else:
        print("⚡ Using cached data")

    return cached_df

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    df = get_data()

    if query:
        results = df[df.apply(lambda row: row.astype(str).str.lower().str.contains(query).any(), axis=1)]
        return results.to_json(orient="records")

    return jsonify([])

if __name__ == "__main__":
    app.run(debug=True)
