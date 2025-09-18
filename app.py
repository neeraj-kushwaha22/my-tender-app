from flask import Flask, render_template, request, jsonify
import pandas as pd

app = Flask(__name__)

# Load your CSV once when the app starts
df = pd.read_csv("yourfile.csv")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q", "").lower()
    if query:
        # Search all columns for the query
        results = df[df.apply(lambda row: row.astype(str).str.lower().str.contains(query).any(), axis=1)]
        return results.to_json(orient="records")
    return jsonify([])

if __name__ == "__main__":
    app.run(debug=True)
