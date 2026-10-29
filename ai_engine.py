
import requests


def generate_plan(telemetry_data, query):
    print(f"[AI Engine] Firing up local AI assistant for query: {query}...")

    local_endpoint = "http://127.0.0.1:11434/api/generate"

    prompt = (
        f"You are an AI schedule assistant. The user asked: '{query}'. "
        "Create a realistic and productive schedule or timetable. "
        "Include time slots (e.g. 08:00 - 10:00) with specific activities. "
        "Keep it concise, actionable, and formatted with bullet points."
    )

    try:
        response = requests.post(
            local_endpoint,
            json={
                "model": "tinyllama",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 150,
                    "temperature": 0.6,
                },
            },
            timeout=45,
        )

        response.raise_for_status()

        plan = response.json().get("response", "").strip()

        if plan:
            return plan

        print("[AI Engine] Empty response. Using static fallback.")
        return _static_fallback(query)

    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"[AI Engine] Local AI failed. Using static fallback: {e}")
        return _static_fallback(query)


def _static_fallback(query):
    """Last resort when the local AI is unavailable."""
    query_lower = query.lower()

    if "week" in query_lower:
        return (
            "📅 Weekly Focus Strategy:\n"
            "• Mon-Tue: Deep Work & Critical Architecture\n"
            "• Wed: Core Feature Development\n"
            "• Thu: Squad Sync & Integration Testing\n"
            "• Fri: Bug Bashes, Review & Weekend Prep"
        )
    elif "priority" in query_lower or "task" in query_lower:
        return (
            "🎯 Prioritized Action Matrix:\n"
            "1. P0 (Immediate): Core blocker bugs & API contract fixes\n"
            "2. P1 (Today): Primary feature requirements & unit tests\n"
            "3. P2 (Upcoming): Performance profiling & code cleanup"
        )

    return (
        "⚡ Daily Focus Timetable:\n"
        "• 08:00 - 09:00 | Standup, Planning & Inbox Zero\n"
        "• 09:00 - 12:00 | Deep Lockdown Coding Block (Sprint 1)\n"
        "• 12:00 - 13:00 | Nutritional Fuel & Screen Disconnect\n"
        "• 13:00 - 16:00 | Collaborative Building & Integration (Sprint 2)\n"
        "• 16:00 - 17:30 | Code Reviews & Retrospective"
    )
