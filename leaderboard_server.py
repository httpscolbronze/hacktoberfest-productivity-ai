from fastapi import FastAPI, HTTPException, Request, Response, status, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import sqlite3
import uvicorn
import os
import re
import time
from collections import defaultdict

app = FastAPI(
    title="Enfoque-AI Secure Leaderboard Server",
    description="Hardened backend for hackathon squad leaderboards and score tracking.",
    version="2.2.0"
)

# Enable CORS for local network collaboration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Always resolve DB path relative to this file
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaderboard.db")

# In-Memory Rate Limiter (sliding window)
_REQUEST_TIMESTAMPS = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 100  # max requests per window per IP

# Allowed characters: alphanumeric, spaces, hyphens, underscores (1 to 30 chars)
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\- ]{1,30}$")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Rate Limiting
        _REQUEST_TIMESTAMPS[client_ip] = [
            t for t in _REQUEST_TIMESTAMPS[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]

        if len(_REQUEST_TIMESTAMPS[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            response = Response(
                content='{"detail": "Rate limit exceeded. Too many requests."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json"
            )
        else:
            _REQUEST_TIMESTAMPS[client_ip].append(now)
            response = await call_next(request)

        # Apply Security Headers to every response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

app.add_middleware(SecurityHeadersMiddleware)


def init_db():
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            username TEXT PRIMARY KEY NOT NULL CHECK(length(username) <= 30 AND length(trim(username)) > 0),
            points INTEGER NOT NULL CHECK(points >= 0 AND points <= 1000000),
            focus_hours REAL NOT NULL CHECK(focus_hours >= 0.0 AND focus_hours <= 1000.0)
        )
    """)
    conn.commit()
    conn.close()

init_db()


@app.post("/update_score")
def update_score(
    username: str = Query(..., min_length=1, max_length=30, description="Player username"),
    points: int = Query(..., ge=0, le=1000000, description="Total points earned"),
    focus_hours: float = Query(..., ge=0.0, le=1000.0, description="Total focus hours logged")
):
    """
    Update or insert player score with strict validation against SQLi, XSS, and invalid numbers.
    """
    clean_username = username.strip()

    # Reject empty or whitespace
    if not clean_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty or whitespace."
        )

    # Reject malicious characters, script tags, special characters
    if not USERNAME_PATTERN.match(clean_username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username contains invalid characters. Use letters, numbers, hyphens, and underscores."
        )

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO scores (username, points, focus_hours)
            VALUES (?, ?, ?)
            ON CONFLICT(username)
            DO UPDATE SET
                points = excluded.points,
                focus_hours = excluded.focus_hours
        """, (clean_username, points, focus_hours))

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": f"Updated score for {clean_username}",
            "data": {
                "username": clean_username,
                "points": points,
                "focus_hours": focus_hours
            }
        }
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database constraint violation: {str(e)}"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the score."
        )


@app.get("/leaderboard")
def get_leaderboard():
    """
    Retrieve squad leaderboard sorted by points descending, then focus hours descending.
    """
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT username, points, focus_hours
            FROM scores
            ORDER BY points DESC, focus_hours DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        leaderboard = [
            {
                "username": r[0],
                "points": r[1],
                "focus_hours": r[2]
            }
            for r in rows
        ]
        return {"status": "success", "leaderboard": leaderboard}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the leaderboard."
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)