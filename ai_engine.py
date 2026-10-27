import ollama
import json
import re

# Gaz's server IP
GAZ_IP = 'http://172.18.254.36:11434'
client = ollama.Client(host=GAZ_IP)
MODEL = 'llama3.2'

def clean_json_response(raw_text: str) -> dict:
    """Helper to safely extract JSON even if the model wraps it in markdown."""
    try:
        # Match anything between curly braces
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(raw_text)
    except Exception:
        # Fallback in case parsing fails
        return {
            "checklist": [
                "Review today's study goals for 25 minutes",
                "Lock non-essential apps",
                "Complete one focused work sprint"
            ],
            "advice": "Keep your screen time in check and stick to high-priority tasks."
        }

def generate_study_plan(user_goals: str, app_usage: dict) -> dict:
    """
    Takes student goals and tracked screen time (from Ghost),
    and returns a structured daily checklist and strict timing advice.
    """
    prompt = f"""
    You are a strict, futuristic AI productivity assistant.
    User's Academic Goals: {user_goals}
    Current Device App Usage (in minutes): {app_usage}

    Analyze the usage. If distracting apps are high, impose strict timings.
    Create a prioritized 3 to 4 item daily checklist for them.

    Respond ONLY in valid JSON matching this exact structure:
    {{
        "advice": "one short, strict sentence on their usage",
        "checklist": [
            "Task 1 description",
            "Task 2 description",
            "Task 3 description"
        ]
    }}
    """
    
    response = client.chat(model=MODEL, messages=[
        {'role': 'user', 'content': prompt}
    ])
    
    return clean_json_response(response['message']['content'])

def get_motivational_quote() -> str:
    """Generates a short, punchy quote for Soap's dark-aesthetic GUI banner."""
    prompt = "Give me one short, aggressive, futuristic motivational quote about discipline and focus. Under 12 words. Do not use quotation marks."
    
    response = client.chat(model=MODEL, messages=[
        {'role': 'user', 'content': prompt}
    ])
    
    return response['message']['content'].strip()