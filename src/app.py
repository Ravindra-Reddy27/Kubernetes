import os
import time
import logging
from contextlib import contextmanager
from typing import Optional, Generator, Any

import psycopg2
from flask import Flask, render_template_string, jsonify, Response

# ------------------------------------------------------------------------------
# Configuration & Setup
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "appdb")
    DB_USER = os.getenv("DB_USER", "user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
    HOSTNAME = os.getenv("HOSTNAME", "local")

app = Flask(__name__)

# ------------------------------------------------------------------------------
# HTML Template (The UI)
# ------------------------------------------------------------------------------
# We use a simple embedded HTML string with internal CSS for styling.
PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HA Platform</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f6f8;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            color: #333;
        }
        .card {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 400px;
            width: 100%;
        }
        h1 { font-size: 1.5rem; margin-bottom: 1rem; color: #2c3e50; }
        .count-box {
            font-size: 3rem;
            font-weight: bold;
            color: #3498db;
            margin: 1rem 0;
        }
        .footer { font-size: 0.85rem; color: #7f8c8d; margin-top: 1.5rem; border-top: 1px solid #eee; padding-top: 1rem;}
    </style>
</head>
<body>
    <div class="card">
        <h1>Welcome to the Platform</h1>
        <p>Total Visits:</p>
        <div class="count-box">{{ count }}</div>
        <div class="footer">
            Served by container: <strong>{{ hostname }}</strong>
        </div>
    </div>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# Database Utilities
# ------------------------------------------------------------------------------
def _create_connection() -> Optional[Any]:
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=Config.DB_HOST,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            return conn
        except psycopg2.OperationalError:
            logger.warning(f"Database not ready. Retrying... ({retries} attempts left)")
            retries -= 1
            time.sleep(2)
    logger.error("Failed to connect to the database after maximum retries.")
    return None

@contextmanager
def db_cursor(commit: bool = False) -> Generator:
    conn = _create_connection()
    if not conn:
        yield None
        return
    try:
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        finally:
            cur.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def init_db() -> None:
    with db_cursor(commit=True) as cur:
        if cur:
            cur.execute('CREATE TABLE IF NOT EXISTS visits (id SERIAL PRIMARY KEY, count INTEGER);')
            cur.execute('SELECT count FROM visits WHERE id = 1;')
            if cur.fetchone() is None:
                cur.execute('INSERT INTO visits (id, count) VALUES (1, 0);')
            logger.info("Database initialized successfully.")

# ------------------------------------------------------------------------------
# Route Handlers
# ------------------------------------------------------------------------------
@app.route('/')
def index():
    """Renders the HTML page with the visitor count."""
    with db_cursor(commit=True) as cur:
        if not cur:
            return "Database Error", 500
        
        cur.execute('UPDATE visits SET count = count + 1 WHERE id = 1 RETURNING count;')
        result = cur.fetchone()
        count = result[0] if result else 0

    # We use render_template_string to inject variables into the HTML above
    return render_template_string(PAGE_TEMPLATE, count=count, hostname=Config.HOSTNAME)

@app.route('/health')
def health() -> tuple[Response, int]:
    """Keep health check as JSON for Kubernetes/Monitoring tools."""
    return jsonify({"status": "healthy"}), 200

# ------------------------------------------------------------------------------
# App Entry Point
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000)