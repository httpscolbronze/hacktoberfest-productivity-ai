import time
import pygetwindow as gw
import psutil
import matplotlib.pyplot as plt

def track_active_windows():
    print("=" * 50)
    print("Active Window Tracker with Chart Started. Press Ctrl+C to stop.")
    print("=" * 50)
    
    time_spent = {}
    current_window = None
    start_time = time.time()

    try:
        while True:
            try:
                window = gw.getActiveWindow()
                if window and window.title.strip():
                    window_title = window.title.strip()
                else:
                    window_title = "Unknown / Desktop"
            except Exception:
                window_title = "Unknown / Desktop"

            now = time.time()

            # Record time spent when switching windows
            if window_title != current_window:
                if current_window is not None:
                    elapsed = now - start_time
                    time_spent[current_window] = time_spent.get(current_window, 0) + elapsed
                    print(f"[Switch] Spent {elapsed:.1f}s on: {current_window}")
                
                current_window = window_title
                start_time = now

            time.sleep(1)

    except KeyboardInterrupt:
        # Record final active window time
        if current_window is not None:
            elapsed = time.time() - start_time
            time_spent[current_window] = time_spent.get(current_window, 0) + elapsed

        print("\n\n" + "=" * 50)
        print("Stopping tracker... Generating visual chart...")
        print("=" * 50)

        if not time_spent:
            print("No data recorded.")
            return

        # Sort windows by total time descending
        sorted_data = sorted(time_spent.items(), key=lambda x: x[1], reverse=True)
        
        # Keep top 8 windows and bundle the rest into "Other Apps" for a clean chart
        if len(sorted_data) > 8:
            top_data = sorted_data[:8]
            other_time = sum(duration for _, duration in sorted_data[8:])
            top_data.append(("Other Apps", other_time))
            sorted_data = top_data

        # Format window titles and convert seconds to minutes
        titles = [item[0][:30] + "..." if len(item[0]) > 30 else item[0] for item in sorted_data]
        durations = [item[1] / 60 for item in sorted_data]

        # Generate Horizontal Bar Chart with adjusted margins to prevent overlapping
        plt.figure(figsize=(10, 6))
        plt.barh(titles[::-1], durations[::-1], color='#4C72B0')
        plt.xlabel('Time Spent (Minutes)', fontsize=12)
        plt.title('Active Window Time Breakdown', fontsize=14, fontweight='bold')
        plt.grid(axis='x', linestyle='--', alpha=0.7)
        
        # Prevents window title labels from getting cut off or overlapping on the left
        plt.subplots_adjust(left=0.35)
        plt.tight_layout()
        
        # Display the chart window
        plt.show()

if __name__ == "__main__":
    track_active_windows()