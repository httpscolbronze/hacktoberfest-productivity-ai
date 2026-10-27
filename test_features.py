from ai_engine import generate_study_plan, get_motivational_quote

print("--- Testing Quote ---")
quote = get_motivational_quote()
print(quote)

print("\n--- Testing Study Planner & Checklist ---")
sample_usage = {"Instagram": 95, "YouTube": 60, "VS Code": 25}
sample_goals = "Prepare for upcoming Hackathon presentation and finish physics revision"

result = generate_study_plan(sample_goals, sample_usage)
print("Advice:", result.get("advice"))
print("Checklist:")
for item in result.get("checklist", []):
    print(f"- [ ] {item}")