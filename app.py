import customtkinter as ctk
import psutil

# ------------------ GLOBAL FUTURISTIC AESTHETICS ------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

BG_DARK = "#0B0F19"         
CARD_BG = "#131C2E"         
CARD_BORDER = "#1E293B"      
ACCENT_CYAN = "#06B6D4"      
ACCENT_PURPLE = "#A855F7"   
ACCENT_GREEN = "#22C55E"    
ACCENT_RED = "#F43F5E"       
TEXT_LIGHT = "#F8FAFC"      
TEXT_MUTED = "#64748B"          

class NexusLockdownSuite(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ FOCUS-AI — HARDCORE LOCKDOWN SUITE")
        self.geometry("1200x780")
        self.configure(fg_color=BG_DARK)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_sidebar()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.pages = {}
        for PageClass in (LockdownDashboardPage, MoodPlannerPage):
            page_name = PageClass.__name__
            frame = PageClass(parent=self.container, controller=self)
            self.pages[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_page("LockdownDashboardPage")

    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#0B0F19")
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        logo = ctk.CTkLabel(self.sidebar, text="⚡ FOCUS-AI", font=("Consolas", 26, "bold"), text_color=ACCENT_CYAN)
        logo.pack(pady=(30, 5), padx=20)

        sub_logo = ctk.CTkLabel(self.sidebar, text="LOCKDOWN PROTOCOL v3.0", font=("Consolas", 9), text_color=ACCENT_RED)
        sub_logo.pack(pady=(0, 20))

        btn_dash = ctk.CTkButton(
            self.sidebar, text="🎯 Command Center", fg_color=CARD_BG, 
            hover_color=ACCENT_CYAN, text_color=TEXT_LIGHT, font=("Helvetica", 13, "bold"),
            command=lambda: self.show_page("LockdownDashboardPage")
        )
        btn_dash.pack(pady=8, padx=20, fill="x")

        btn_mood = ctk.CTkButton(
            self.sidebar, text="🧠 AI Mood Planner", fg_color=CARD_BG, 
            hover_color=ACCENT_CYAN, text_color=TEXT_LIGHT, font=("Helvetica", 13, "bold"),
            command=lambda: self.show_page("MoodPlannerPage")
        )
        btn_mood.pack(pady=8, padx=20, fill="x")

        # Lockdown Mode Toggle Switch
        lock_frame = ctk.CTkFrame(self.sidebar, fg_color=CARD_BG, corner_radius=12, border_color=ACCENT_RED, border_width=1)
        lock_frame.pack(side="bottom", pady=20, padx=15, fill="x")
        
        ctk.CTkLabel(lock_frame, text="🔒 HARDCORE LOCK", text_color=ACCENT_RED, font=("Consolas", 11, "bold")).pack(pady=(10, 2))
        
        self.lock_switch = ctk.CTkSwitch(lock_frame, text="Always on Top", text_color=TEXT_LIGHT, command=self.toggle_lockdown, progress_color=ACCENT_RED)
        self.lock_switch.pack(pady=(5, 12), padx=10)

    def toggle_lockdown(self):
        if self.lock_switch.get() == 1:
            self.attributes("-topmost", True)
        else:
            self.attributes("-topmost", False)

    def show_page(self, page_name):
        frame = self.pages[page_name]
        frame.tkraise()

# ------------------ PAGE 1: LOCKDOWN DASHBOARD ------------------
class LockdownDashboardPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. HARDCORE MOTIVATIONAL BANNER
        banner = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=14, border_color=ACCENT_RED, border_width=1)
        banner.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(banner, text="🚨 SQUAD DIRECTIVE: NO DISTRACTIONS ALLOWED", font=("Consolas", 11, "bold"), text_color=ACCENT_RED).pack(anchor="w", pady=(15, 5), padx=20)
        ctk.CTkLabel(
            banner, text='"Lock in right now. Every line of code written today secures the hackathon victory tomorrow."',
            font=("Helvetica", 14, "italic"), text_color=TEXT_LIGHT, wraplength=750
        ).pack(anchor="w", pady=(0, 15), padx=20)

        # 2. POMODORO FOCUS ENGINE
        timer_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=14, border_color=CARD_BORDER, border_width=1)
        timer_card.pack(fill="x", pady=10)

        ctk.CTkLabel(timer_card, text="⏱️ LOCKDOWN SPRINT TIMER", font=("Consolas", 12, "bold"), text_color=ACCENT_CYAN).pack(anchor="w", pady=(15, 5), padx=20)
        
        self.time_left = 25 * 60
        self.timer_running = False

        self.timer_display = ctk.CTkLabel(timer_card, text="25:00", font=("Consolas", 48, "bold"), text_color=TEXT_LIGHT)
        self.timer_display.pack(pady=5)

        btn_box = ctk.CTkFrame(timer_card, fg_color="transparent")
        btn_box.pack(pady=(0, 15))

        self.btn_start = ctk.CTkButton(btn_box, text="🚀 Start Locking In", fg_color=ACCENT_CYAN, text_color="black", font=("Helvetica", 12, "bold"), width=130, command=self.toggle_timer)
        self.btn_start.pack(side="left", padx=5)

        ctk.CTkButton(btn_box, text="Reset", fg_color="#374151", text_color=TEXT_LIGHT, font=("Helvetica", 12, "bold"), width=80, command=self.reset_timer).pack(side="left", padx=5)

        # 3. STUDY SQUAD CO-OP GOAL CARD
        coop_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=14, border_color=CARD_BORDER, border_width=1)
        coop_card.pack(fill="x", pady=15)

        ctk.CTkLabel(coop_card, text="🤝 NIU HACKATHON SQUAD CO-OP GOAL", font=("Consolas", 12, "bold"), text_color=ACCENT_PURPLE).pack(anchor="w", pady=(15, 5), padx=20)
        ctk.CTkLabel(coop_card, text="Squad Target: 15.0 / 20.0 Hours Logged Today", font=("Helvetica", 13, "bold"), text_color=TEXT_LIGHT).pack(anchor="w", padx=20, pady=5)

        self.coop_bar = ctk.CTkProgressBar(coop_card, progress_color=ACCENT_PURPLE, fg_color="#1E293B", height=12)
        self.coop_bar.set(0.75)
        self.coop_bar.pack(fill="x", padx=20, pady=(5, 15))

        # 4. LIVE LEADERBOARD
        lb_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=14, border_color=CARD_BORDER, border_width=1)
        lb_card.pack(fill="x", pady=10)

        ctk.CTkLabel(lb_card, text="🏆 SQUAD RANKINGS", font=("Consolas", 12, "bold"), text_color=TEXT_LIGHT).pack(anchor="w", pady=(15, 10), padx=20)

        for name, stats in [("🥇 Ghost", "520 XP | 92% Lockdown Score"), ("🥈 Price", "480 XP | 88% Lockdown Score"), ("🥉 Soap (You)", "410 XP | 75% Lockdown Score")]:
            row = ctk.CTkFrame(lb_card, fg_color="#1F2937" if "You" in name else "transparent", corner_radius=8)
            row.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(row, text=name, font=("Consolas", 13, "bold"), text_color=ACCENT_CYAN if "You" in name else TEXT_LIGHT).pack(side="left", padx=15, pady=8)
            ctk.CTkLabel(row, text=stats, font=("Helvetica", 11), text_color=TEXT_MUTED).pack(side="right", padx=15, pady=8)

    def toggle_timer(self):
        self.timer_running = not self.timer_running
        if self.timer_running:
            self.btn_start.configure(text="Pause", fg_color=ACCENT_RED)
            self.run_timer()
        else:
            self.btn_start.configure(text="Resume", fg_color=ACCENT_CYAN)

    def run_timer(self):
        if self.timer_running and self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_display.configure(text=f"{mins:02d}:{secs:02d}")
            self.after(1000, self.run_timer)
        elif self.time_left == 0:
            self.timer_display.configure(text="LOCKDOWN SESSION COMPLETE! ⚡")
            self.timer_running = False

    def reset_timer(self):
        self.timer_running = False
        self.time_left = 25 * 60
        self.timer_display.configure(text="25:00")
        self.btn_start.configure(text="🚀 Start Locking In", fg_color=ACCENT_CYAN)

# ------------------ PAGE 2: MOOD PLANNER ------------------
class MoodPlannerPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        title_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=12, border_color=CARD_BORDER, border_width=1)
        title_card.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(title_card, text="🧠 AI Burnout-Shield & Timetable Generator", font=("Helvetica", 18, "bold"), text_color=ACCENT_CYAN).pack(anchor="w", pady=15, padx=20)
        ctk.CTkLabel(title_card, text="Tell the AI your current energy level to generate an optimized lockdown routine.", font=("Helvetica", 13), text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(0, 15))

        input_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=12, border_color=CARD_BORDER, border_width=1)
        input_card.pack(fill="x", pady=10)
        
        ctk.CTkLabel(input_card, text="How are you feeling right now?", font=("Helvetica", 14, "bold"), text_color=TEXT_LIGHT).pack(anchor="w", pady=(15, 5), padx=20)
        
        self.mood_entry = ctk.CTkEntry(input_card, placeholder_text="e.g., Exhausted, hyper-focused, stressed...", height=40, font=("Helvetica", 13))
        self.mood_entry.pack(fill="x", padx=20, pady=10)

        gen_btn = ctk.CTkButton(input_card, text="✨ Generate Lockdown Routine", fg_color=ACCENT_CYAN, text_color="black", font=("Helvetica", 14, "bold"), hover_color=ACCENT_PURPLE, command=self.generate_timetable)
        gen_btn.pack(pady=(5, 20), padx=20, anchor="w")

        self.result_card = ctk.CTkFrame(scroll, fg_color=CARD_BG, corner_radius=12, border_color=CARD_BORDER, border_width=1)
        self.result_card.pack(fill="x", pady=10)
        
        ctk.CTkLabel(self.result_card, text="📅 Your Active Lockdown Schedule", font=("Helvetica", 16, "bold"), text_color=ACCENT_CYAN).pack(anchor="w", pady=(15, 10), padx=20)
        
        self.timetable_output = ctk.CTkLabel(self.result_card, text="Type your mood above to build your schedule.", font=("Consolas", 13), text_color=TEXT_LIGHT, justify="left")
        self.timetable_output.pack(anchor="w", pady=(0, 20), padx=20)

    def generate_timetable(self):
        mood = self.mood_entry.get().strip().lower()
        if not mood:
            self.timetable_output.configure(text="⚠️ Enter your mood first!")
            return

        if "stress" in mood or "tired" in mood or "exhausted" in mood:
            schedule = (
                "🛡️ **Burnout Shield Recovery Protocol:**\n\n"
                "• 5 Min : Hydration & eye-strain breathing break\n"
                "• 25 Min: Low-friction code review (No heavy lifting)\n"
                "• 10 Min: Physical stretch walk\n"
                "• 25 Min: Steady Pomodoro execution sprint"
            )
        else:
            schedule = (
                "🔥 **Hardcore Execution Schedule:**\n\n"
                "• 45 Min: Deep work block (Zero browser tabs)\n"
                "• 10 Min: Quick sync with squadmates (Ghost & Price)\n"
                "• 45 Min: Bug hunting & repository integration sprint"
            )

        self.timetable_output.configure(text=schedule)

if __name__ == "__main__":
    app = NexusLockdownSuite()
    app.mainloop()