import time
import json
import subprocess
import matplotlib.pyplot as plt


def get_active_window_title():
    """Get the focused window title from Hyprland."""
    try:
        result = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )

        window = json.loads(result.stdout)
        title = window.get("title", "").strip()

        return title or "Unknown / Desktop"

    except (
        subprocess.SubprocessError,
        json.JSONDecodeError,
        OSError,
    ):
        return "Unknown / Desktop"


def track_active_windows(stop_event=None):
    """Track active windows until stop_event is set.

    Args:
        stop_event: threading.Event object. If set, stops tracking.
    """
    print("=" * 50)
    print("Active Window Tracker Started. Press Ctrl+C to stop.")
    print("=" * 50)

    time_spent = {}
    current_window = None
    start_time = time.time()

    try:
        while True:
            # Check if external stop signal received
            if stop_event and stop_event.is_set():
                print("[Tracker] Stopping due to stop_event signal.")
                break

            window_title = get_active_window_title()
            now = time.time()

            if window_title != current_window:
                if current_window is not None:
                    elapsed = now - start_time
                    time_spent[current_window] = (
                        time_spent.get(current_window, 0) + elapsed
                    )
                    print(
                        f"[Switch] Spent {elapsed:.1f}s on: "
                        f"{current_window}"
                    )

                current_window = window_title
                start_time = now

            time.sleep(1)

    except KeyboardInterrupt:
        print("[Tracker] KeyboardInterrupt received.")
        # Continue to finally block
        pass

    finally:
        # Generate chart if any data was recorded
        if time_spent:
            print("\n\n" + "=" * 50)
            print("Stopping tracker... Generating visual chart...")
            print("=" * 50)

            sorted_data = sorted(
                time_spent.items(),
                key=lambda item: item[1],
                reverse=True,
            )

            if len(sorted_data) > 8:
                top_data = sorted_data[:8]
                other_time = sum(
                    duration for _, duration in sorted_data[8:]
                )
                top_data.append(("Other Apps", other_time))
                sorted_data = top_data

            titles = [
                item[0][:30] + "..."
                if len(item[0]) > 30 else item[0]
                for item in sorted_data
            ]
            durations = [item[1] / 60 for item in sorted_data]

            plt.figure(figsize=(10, 6))
            plt.barh(titles[::-1], durations[::-1], color="#4C72B0")
            plt.xlabel("Time Spent (Minutes)", fontsize=12)
            plt.title(
                "Active Window Time Breakdown",
                fontsize=14,
                fontweight="bold",
            )
            plt.grid(axis="x", linestyle="--", alpha=0.7)
            plt.subplots_adjust(left=0.35)
            plt.tight_layout()
            plt.show()
        else:
            print("[Tracker] No data recorded.")


if __name__ == "__main__":
    track_active_windows()
