import os
import sqlite3
from datetime import datetime, timezone

import joblib
import pandas as pd
from flask import Flask, jsonify, render_template, request

MODEL_PATH = "news_model.joblib"
DB_PATH = "data/posts.db"

app = Flask(__name__)

model = joblib.load(MODEL_PATH)
CATEGORIES = list(map(str, getattr(model, "classes_", ["unknown"])))


def ensure_dir_for_file(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    ensure_dir_for_file(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                created_at TEXT NOT NULL,      -- kdy to uživatel vložil (UTC ISO)
                updated_at TEXT,               -- poslední update (UTC ISO)
                published_at TEXT NOT NULL,    -- "datum článku"

                title TEXT,
                content TEXT NOT NULL,

                predicted_category TEXT,
                final_category TEXT NOT NULL,

                text_length INTEGER,
                hour INTEGER,
                weekday INTEGER,
                month INTEGER
            )
            """
        )

        # pro jistotu: když db existuje ze starší verze, updated_at tam být nemusí
        def try_add(col_sql: str) -> None:
            try:
                conn.execute(col_sql)
            except sqlite3.OperationalError:
                pass

        try_add("ALTER TABLE posts ADD COLUMN updated_at TEXT")

        conn.commit()


init_db()


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt_utc(published_at_raw):
    """Parse ISO/datetime-ish na UTC datetime. Když neplatné -> now(UTC)."""
    if published_at_raw:
        dt = pd.to_datetime(published_at_raw, errors="coerce", utc=True)
        if pd.isna(dt):
            return datetime.now(timezone.utc)
        return dt.to_pydatetime()
    return datetime.now(timezone.utc)


def build_features(payload: dict) -> dict:
    title = payload.get("title", "") or ""
    content = payload.get("content", "") or ""

    dt = parse_dt_utc(payload.get("published_at"))

    return {
        "title": title,
        "content": content,
        "text_length": len(content),
        "hour": int(dt.hour),
        "weekday": int(dt.weekday()),
        "month": int(dt.month),
        "published_at": dt.isoformat(),
    }


def predict_category_from_features(features: dict) -> str:
    X = pd.DataFrame([{
        "title": features["title"],
        "content": features["content"],
        "text_length": features["text_length"],
        "hour": features["hour"],
        "weekday": features["weekday"],
        "month": features["month"],
    }])
    return str(model.predict(X)[0])


@app.get("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.get("/api/categories")
def api_categories():
    return jsonify({"categories": CATEGORIES})


@app.post("/api/predict")
def api_predict():
    payload = request.get_json(force=True, silent=True) or {}
    content = (payload.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    features = build_features(payload)
    pred = predict_category_from_features(features)

    return jsonify({
        "predicted_category": pred,
        "published_at": features["published_at"],
        "hour": features["hour"],
        "weekday": features["weekday"],
        "month": features["month"],
        "text_length": features["text_length"],
    })


@app.post("/api/posts")
def api_create_post():
    payload = request.get_json(force=True, silent=True) or {}
    content = (payload.get("content", "") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    features = build_features(payload)

    predicted = payload.get("predicted_category") or predict_category_from_features(features)
    final_category = payload.get("final_category") or predicted
    if final_category not in CATEGORIES:
        return jsonify({"error": "final_category must be one of model categories"}), 400

    created_at = now_iso_utc()
    updated_at = None

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (
                created_at, updated_at, published_at,
                title, content,
                predicted_category, final_category,
                text_length, hour, weekday, month
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                updated_at,
                features["published_at"],
                features["title"],
                features["content"],
                predicted,
                final_category,
                features["text_length"],
                features["hour"],
                features["weekday"],
                features["month"],
            ),
        )
        conn.commit()
        post_id = int(cur.lastrowid)

    return jsonify({"id": post_id, "created_at": created_at}), 201


@app.get("/api/posts")
def api_list_posts():
    limit_raw = request.args.get("limit", "200")
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 500))

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id, created_at, updated_at, published_at,
                title, content,
                predicted_category, final_category
            FROM posts
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return jsonify({"posts": [dict(r) for r in rows]})


@app.get("/api/posts/<int:post_id>")
def api_get_post(post_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                id, created_at, updated_at, published_at,
                title, content,
                predicted_category, final_category,
                text_length, hour, weekday, month
            FROM posts
            WHERE id = ?
            """,
            (post_id,),
        ).fetchone()

    if not row:
        return jsonify({"error": "post not found"}), 404

    return jsonify(dict(row))


@app.patch("/api/posts/<int:post_id>")
def api_update_post(post_id: int):
    payload = request.get_json(force=True, silent=True) or {}

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            return jsonify({"error": "post not found"}), 404

        current = dict(row)

        new_title = payload.get("title", current.get("title"))
        new_content = payload.get("content", current.get("content"))
        new_published_at = payload.get("published_at", current.get("published_at"))
        new_final_category = payload.get("final_category", current.get("final_category"))

        if not new_final_category:
            return jsonify({"error": "final_category is required"}), 400
        if new_final_category not in CATEGORIES:
            return jsonify({"error": "final_category must be one of model categories"}), 400

        recompute = (
            (new_title != current.get("title"))
            or (new_content != current.get("content"))
            or (new_published_at != current.get("published_at"))
        )

        updated_at = now_iso_utc()

        if recompute:
            features = build_features({
                "title": new_title,
                "content": new_content,
                "published_at": new_published_at,
            })
            new_predicted = payload.get("predicted_category") or predict_category_from_features(features)

            conn.execute(
                """
                UPDATE posts SET
                    updated_at = ?,
                    published_at = ?,
                    title = ?,
                    content = ?,
                    predicted_category = ?,
                    final_category = ?,
                    text_length = ?,
                    hour = ?,
                    weekday = ?,
                    month = ?
                WHERE id = ?
                """,
                (
                    updated_at,
                    features["published_at"],
                    features["title"],
                    features["content"],
                    new_predicted,
                    new_final_category,
                    features["text_length"],
                    features["hour"],
                    features["weekday"],
                    features["month"],
                    post_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE posts SET
                    updated_at = ?,
                    final_category = ?
                WHERE id = ?
                """,
                (updated_at, new_final_category, post_id),
            )

        conn.commit()

    return jsonify({"ok": True, "updated_at": updated_at})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)