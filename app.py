from flask import Flask, request, jsonify, redirect, abort
import sqlite3
import string
import random
import os
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from flask import render_template

app = Flask(__name__)
@app.route("/")
def home():
    return render_template("index.html")


# ----------------------------
# DB configuration
# ----------------------------
DB_FILE = os.environ.get("DB_FILE", "urls.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------
# Prometheus Metrics
# ----------------------------

# Counters
URLS_SHORTENED = Counter(
    "urls_shortened_total",
    "Total number of successfully shortened URLs"
)

SUCCESSFUL_REDIRECTS = Counter(
    "successful_redirects_total",
    "Total number of successful URL redirects"
)

FAILED_LOOKUPS = Counter(
    "failed_lookups_total",
    "Total number of failed short code lookups (404s)"
)

# Histograms for latency
SHORTEN_LATENCY = Histogram(
    "shorten_request_latency_seconds",
    "Latency for POST /shorten requests"
)

REDIRECT_LATENCY = Histogram(
    "redirect_request_latency_seconds",
    "Latency for GET /<code> requests"
)

# ----------------------------
# Initialize DB
# ----------------------------
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE urls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT UNIQUE NOT NULL,
                        long_url TEXT NOT NULL
                    )''')
        conn.commit()
        conn.close()


def generate_code(length=6):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# ----------------------------
# Metrics Endpoint
# ----------------------------
@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


# ----------------------------
# POST /shorten
# ----------------------------
@app.route('/shorten', methods=['POST'])
@SHORTEN_LATENCY.time()
def shorten_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'Missing "url" field'}), 400

    long_url = data['url']

    # Create unique short code
    conn = get_db_connection()
    c = conn.cursor()

    while True:
        code = generate_code()
        c.execute('SELECT * FROM urls WHERE code = ?', (code,))
        if not c.fetchone():
            break

    # Insert mapping
    c.execute('INSERT INTO urls (code, long_url) VALUES (?, ?)', (code, long_url))
    conn.commit()
    conn.close()

    URLS_SHORTENED.inc()  # increment counter

    short_url = request.host_url + code
    return jsonify({'short_url': short_url}), 201


# ----------------------------
# GET /<code>
# ----------------------------
@app.route('/<code>', methods=['GET'])
@REDIRECT_LATENCY.time()
def redirect_to_long_url(code):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT long_url FROM urls WHERE code = ?', (code,))
    result = c.fetchone()
    conn.close()

    if result:
        SUCCESSFUL_REDIRECTS.inc()
        return redirect(result['long_url'])
    else:
        FAILED_LOOKUPS.inc()
        abort(404, description="Short URL not found")


# ----------------------------
# Main
# ----------------------------
if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=5000)