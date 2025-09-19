from flask import Flask, render_template, request, jsonify
import pandas as pd

app = Flask(__name__)

# Google Sheets live CSV URL
CSV_URL = "https://docs.google.com/spreadsheets/d/1IcLsng5J0Iwl9bTTCyIWiLpVdyWpbCOmUxXmuaboBho/gviz/tq?tqx=out:csv"

def load_data():
    return pd.read_csv(CSV_URL)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    df = load_data()  # always load the latest data
    if query:
        # Search all columns for the query
        results = df[df.apply(
            lambda row: row.astype(str).str.lower().str.contains(query).any(),
            axis=1
        )]
        return results.to_json(orient="records")
    return df.to_json(orient="records")  # show full list if no query

if __name__ == "__main__":
    app.run(debug=True)
