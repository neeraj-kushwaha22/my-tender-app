from flask import Flask, render_template, request, jsonify
import pandas as pd
import time

app = Flask(__name__)

# Google Sheets CSV link
CSV_URL = "https://docs.google.com/spreadsheets/d/1IcLsng5J0Iwl9bTTCyIWiLpVdyWpbCOmUxXmuaboBho/gviz/tq?tqx=out:csv"

# Cache setup
df_cache = None
last_fetched = 0
CACHE_TIMEOUT = 300  # 5 minutes

def get_data():
    global df_cache, last_fetched
    now = time.time()
    if df_cache is None or (now - last_fetched) > CACHE_TIMEOUT:
        df_cache = pd.read_csv(CSV_URL)
        last_fetched = now
    return df_cache

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    df = get_data()
    if query:
        # Search all columns for the query
        results = df[df.apply(
            lambda row: row.astype(str).str.lower().str.contains(query).any(),
            axis=1
        )]
    else:
        # No query → return full dataset
        results = df
    return results.to_json(orient="records")

if __name__ == "__main__":
    app.run(debug=True)
