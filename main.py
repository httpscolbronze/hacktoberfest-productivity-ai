import threading
import queue
import uvicorn
import requests
import os

import app as soap_gui
import gui_Tracker as ghost_tracker
import leaderboard_server as gaz_server
import ai_engine


# Gaz's AI Server Configuration
GAZ_IP = "172.18.254.36"  # Update this with Gaz's actual IP
AI_MODEL = "llama3.2"     # Using Llama 3.2 on Gaz's gaming laptop

# Results from background workers are consumed by the GUI thread.
result_queue = queue.Queue()

# Thread control events
_tracker_stop_event = threading.Event()
_server_ready_event = threading.Event()


def run_ghost_tracker(stop_event):
    """Launch ghost's window tracker with external stop control."""
    print("[Price] Ghost's tracker launching...")
    try:
        ghost_tracker.track_active_windows(stop_event=stop_event)
    except Exception as exc:
        print(f"[Ghost Module Error] {exc}")


def run_gaz_server():
    """Start leaderboard API server. Blocks until the server is ready."""
    print("[Price] Starting leaderboard API on port 8000...")
    # Ensure we run from the script directory so DB paths resolve correctly
    original_cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    try:
        # Configure uvicorn to signal when ready
        # host="0.0.0.0" allows connections from ANY PC on the network
        config = uvicorn.Config(
            gaz_server.app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
        )
        server = uvicorn.Server(config=config)

        # Start server in a way we can wait for it to be ready
        threading.Thread(
            target=lambda: server.run(),
            daemon=True,
            name="GazLeaderboard",
        ).start()

        # Wait briefly for server to start accepting connections
        import time
        time.sleep(0.5)
        _server_ready_event.set()

    except Exception as exc:
        print(f"[Gaz Server Error] {exc}")
    finally:
        os.chdir(original_cwd)


def generate_plan_in_background(query):
    """Run network and local AI calls without blocking the GUI."""
    try:
        endpoint = f"http://{GAZ_IP}:11434/api/generate"
        prompt = (
            f"You are an expert AI Schedule & Focus Assistant. "
            f"The user requests: '{query}'. "
            "Generate a structured, actionable daily/weekly schedule or plan. "
            "Use clear time blocks, bullet points, and practical focus advice. "
            "Be motivating, concise, and structured."
        )

        print(f"[Price] Contacting Gaz's AI server ({GAZ_IP}) running {AI_MODEL}...")

        response = requests.post(
            endpoint,
            json={
                "model": AI_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()

        plan = response.json().get("response", "").strip()
        if not plan:
            raise ValueError(f"Gaz's AI ({AI_MODEL}) returned an empty response.")

        result_queue.put(("plan", plan, f"{AI_MODEL} on Gaz's PC"))
        return

    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"[Warning] Remote AI unavailable: {exc}")

    try:
        print("[Price] Trying local AI fallback...")
        plan = ai_engine.generate_plan(
            {"status": "tracking_active"},
            query,
        )

        if not isinstance(plan, str) or not plan.strip():
            raise ValueError("Local AI returned an empty or invalid plan.")

        result_queue.put(("plan", plan, "Local AI / fallback"))
    except Exception as exc:
        print(f"[AI Error] Local fallback failed: {exc}")
        result_queue.put(("default", "", "Soap's built-in planner"))


def main():
    print("=" * 50)
    print("FOCUS-AI MASTER CONTROLLER")
    print("=" * 50)

    # Launch ghost's window tracker with stop event control
    threading.Thread(
        target=run_ghost_tracker,
        args=(_tracker_stop_event,),
        daemon=True,
        name="GhostTracker",
    ).start()

    # Start the leaderboard server in its own thread
    threading.Thread(
        target=run_gaz_server,
        daemon=True,
        name="GazLeaderboard",
    ).start()

    # Wait for server to be ready
    import time
    while not _server_ready_event.is_set():
        time.sleep(0.1)

    # Save reference to original generate_plan for fallback
    original_generate = soap_gui.AIAssistantPage.generate_plan

    def hijacked_generate(self):
        # Get query from textbox
        query = self.query_entry.get("1.0", "end").strip()

        if not query or query.startswith("e.g.,"):
            self.plan_output.configure(
                text="⚠️ Please enter your planning request first!"
            )
            return

        if getattr(self, "_ai_request_active", False):
            return

        self._ai_request_active = True
        self.plan_output.configure(
            text="📡 Generating your plan...\n"
                 "Trying the squad AI, then local AI assistant if needed."
        )

        def worker():
            generate_plan_in_background(query)

        threading.Thread(
            target=worker,
            daemon=True,
            name="AIRequest",
        ).start()

        def check_results():
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return

            try:
                result_type, plan, source = result_queue.get_nowait()
            except queue.Empty:
                if self.winfo_exists():
                    self.after(100, check_results)
                return

            self._ai_request_active = False

            if not self.winfo_exists():
                return

            if result_type == "plan":
                self.add_to_history("You", query)
                self.add_to_history("AI Assistant", f"{source}:\n\n{plan}")
                self.plan_output.configure(
                    text=f"🧠 {source}:\n\n{plan}"
                )
            else:
                print("[Price] Using Assistant's local planner.")
                original_generate(self)

        self.after(100, check_results)

    # Replace AIAssistantPage.generate_plan with our AI-enhanced version
    soap_gui.AIAssistantPage.generate_plan = hijacked_generate

    print("[Price] Launching Focus-AI interface...")

    # Create main window with the animated reveal splash screen
    ui_app = soap_gui.NexusLockdownSuite(with_splash=True)

    # Start mainloop
    ui_app.mainloop()

    # Clean up tracker on exit
    print("[Price] Shutting down...")
    _tracker_stop_event.set()


if __name__ == "__main__":
    main()