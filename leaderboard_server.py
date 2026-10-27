from fastapi import FastAPI
import sqlite3
import uvicorn

app = FastAPI()

def init_db():
    conn = sqlite3.connect("leaderboard.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            username TEXT PRIMARY KEY,
            points INTEGER,
            focus_hours REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.post("/update_score")
def update_score(username: str, points: int, focus_hours: float):
    conn = sqlite3.connect("sqlite_db.db") # wait, let's keep it leaderboard.db
    conn = sqlite3.connect("leaderboard.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scores (username, points, focus_hours) 
        VALUES (?, ?, ?)
        ON CONFLICT(username) 
        DO UPDATE SET points=excluded.points, focus_hours=excluded.focus_hours
    """, (username, points, focus_hours))
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Updated score for {username}"}

@app.get("/leaderboard")
def get_leaderboard():
    conn = sqlite3.connect("leaderboard.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, points, focus_hours FROM scores ORDER BY points DESC")
    rows = cursor.fetchall()
    conn.close()

    leaderboard = [{"username": r[0], "points": r[1], "focus_hours": r[2]} for r in rows]
    return {"leaderboard": leaderboard}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)