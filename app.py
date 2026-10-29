import array
import math
import queue
import threading
import time
import tkinter as tk
from datetime import datetime

import requests
import customtkinter as ctk


# ------------------ GLOBAL AESTHETICS ------------------

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


# ------------------ SETTINGS ------------------

SPEECH_LANGUAGE = "en-IN"
MIC_DEVICE_INDEX = None

LEADERBOARD_URL = "http://localhost:8000"

SPLASH_DURATION = 4.2


# ------------------ AUDIO HELPERS ------------------

def _rms(raw):
    """Loudness of 16-bit mono audio without audioop."""
    usable = len(raw) - (len(raw) % 2)

    if usable <= 0:
        return 0.0

    samples = array.array("h")
    samples.frombytes(raw[:usable])

    return math.sqrt(
        sum(sample * sample for sample in samples) / len(samples)
    )


def capture_audio(
    read_chunk,
    sample_rate,
    chunk,
    stop_event,
    emit,
    calibrate_s=0.6,
    pause_s=1.8,
    no_speech_timeout_s=15.0,
    max_total_s=60.0,
):
    """
    Record until stopped, speech pauses, or a timeout is reached.

    Returns:
        (audio_bytes, speech_detected, reason)

    reason:
        "manual", "pause", "timeout", or "max"
    """
    chunk_s = chunk / float(sample_rate)
    frames = []
    levels = []

    # Estimate ambient noise.
    for _ in range(max(1, int(calibrate_s / chunk_s))):
        if stop_event.is_set():
            break

        raw = read_chunk(chunk)

        if not raw:
            break

        frames.append(raw)
        levels.append(_rms(raw))

    ambient = sorted(levels)[len(levels) // 2] if levels else 0.0
    threshold = max(ambient * 2.0, ambient + 120.0, 200.0)

    emit(("ready", threshold))

    pre_chunks = max(1, int(0.5 / chunk_s))
    speech_idx = None
    silence = 0.0
    total = 0.0
    reason = "manual"

    while not stop_event.is_set():
        raw = read_chunk(chunk)

        if not raw:
            break

        frames.append(raw)

        level = _rms(raw)
        emit(("level", level, threshold))

        total += chunk_s

        if level > threshold:
            if speech_idx is None:
                speech_idx = max(
                    0,
                    len(frames) - 1 - pre_chunks,
                )

            silence = 0.0

        elif speech_idx is not None:
            silence += chunk_s

            if silence >= pause_s:
                reason = "pause"
                break

        if speech_idx is None and total >= no_speech_timeout_s:
            reason = "timeout"
            break

        if total >= max_total_s:
            reason = "max"
            break

    start = speech_idx if speech_idx is not None else 0

    return (
        b"".join(frames[start:]),
        speech_idx is not None,
        reason,
    )


# ------------------ LEADERBOARD API ------------------

def api_get_leaderboard():
    """
    Return (leaderboard, error_message).

    Keeping errors separate avoids treating an unavailable server
    as a genuinely empty leaderboard.
    """
    try:
        response = requests.get(
            f"{LEADERBOARD_URL}/leaderboard",
            timeout=3,
        )
        response.raise_for_status()

        data = response.json().get("leaderboard", [])

        if not isinstance(data, list):
            raise ValueError("Invalid leaderboard response")

        return data, None

    except (requests.RequestException, ValueError, TypeError) as exc:
        return [], str(exc)


def api_update_score(username, points, focus_hours):
    """Return (success, error_message)."""
    try:
        response = requests.post(
            f"{LEADERBOARD_URL}/update_score",
            params={
                "username": username,
                "points": points,
                "focus_hours": focus_hours,
            },
            timeout=3,
        )
        response.raise_for_status()

        return True, None

    except requests.RequestException as exc:
        return False, str(exc)


# ------------------ FUTURISTIC LOADING SPLASH ------------------

class LoadingSplash(ctk.CTkFrame):
    """
    Responsive, canvas-based splash.

    Features:
        - Counter-rotating orbital rings
        - Pulsing central focus mark
        - Subtle animated starfield
        - Eased, time-based progress
        - Slide-away reveal
        - One animation callback targeting roughly 60 FPS

    The percentage is decorative, not backend readiness.
    """

    FRAME_MS = 16
    EXIT_SECONDS = 0.70

    BG = "#080D18"
    CYAN = "#35E4F4"
    PURPLE = "#A78BFA"
    WHITE = "#EDF7FF"
    MUTED = "#71859F"

    def __init__(self, parent, duration=SPLASH_DURATION):
        super().__init__(
            parent,
            fg_color=self.BG,
            corner_radius=0,
        )

        self.duration = max(0.5, float(duration))

        self._job = None
        self._closed = False
        self._started = None
        self._size = None

        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0

        self.place(
            x=0,
            y=0,
            relwidth=1,
            relheight=1,
        )
        self.tkraise()

        self.canvas = tk.Canvas(
            self,
            bg=self.BG,
            highlightthickness=0,
            borderwidth=0,
            takefocus=False,
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_resize)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self._job = self.after(0, self._animate)

    @staticmethod
    def _clamp(value):
        return max(0.0, min(1.0, value))

    @classmethod
    def _smooth(cls, value):
        value = cls._clamp(value)
        return value * value * (3.0 - 2.0 * value)

    @classmethod
    def _ease_out_cubic(cls, value):
        value = cls._clamp(value)
        return 1.0 - (1.0 - value) ** 3

    @staticmethod
    def _mix(first, second, amount):
        """Blend opaque colors; Canvas items do not support alpha."""
        amount = max(0.0, min(1.0, amount))

        first_rgb = tuple(
            int(first[index:index + 2], 16)
            for index in (1, 3, 5)
        )
        second_rgb = tuple(
            int(second[index:index + 2], 16)
            for index in (1, 3, 5)
        )

        channels = [
            round(a + (b - a) * amount)
            for a, b in zip(first_rgb, second_rgb)
        ]

        return "#{:02x}{:02x}{:02x}".format(*channels)

    def _xy(self, *coordinates):
        """Transform design coordinates to canvas coordinates."""
        return [
            value * self._scale
            + (self._ox if index % 2 == 0 else self._oy)
            for index, value in enumerate(coordinates)
        ]

    def _font(self, size, weight="normal"):
        # Negative sizes specify pixels.
        return (
            "Consolas",
            -max(8, round(size * self._scale)),
            weight,
        )

    def _line(self, *coordinates, **options):
        width = options.pop("width", 1)

        return self.canvas.create_line(
            *self._xy(*coordinates),
            width=max(1, width * self._scale),
            **options,
        )

    def _text(self, x, y, text, size, color, **options):
        weight = options.pop("weight", "normal")

        return self.canvas.create_text(
            *self._xy(x, y),
            text=text,
            font=self._font(size, weight),
            fill=color,
            **options,
        )

    def _on_resize(self, event):
        size = (event.width, event.height)

        if size == self._size or min(size) < 10:
            return

        self._size = size
        self._scale = min(
            event.width / 880,
            event.height / 600,
        )

        self._ox = (
            event.width - 800 * self._scale
        ) / 2

        self._oy = (
            event.height - 520 * self._scale
        ) / 2

        self._build_scene()

    def _build_scene(self):
        """Rebuild only on resize; reuse objects during animation."""
        canvas = self.canvas
        canvas.delete("all")

        # Background grid.
        for x in range(40, 801, 40):
            self._line(
                x, 30, x, 490,
                fill="#0E1929",
            )

        for y in range(30, 491, 40):
            self._line(
                40, y, 760, y,
                fill="#0E1929",
            )

        # Deterministic ambient particles.
        self._stars = []

        for index in range(32):
            x = 45 + ((index * 137) % 710)
            y = 35 + ((index * 89) % 440)
            radius = 0.8 + (index % 3) * 0.35

            item = canvas.create_oval(
                *self._xy(
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius,
                ),
                fill="#29485D",
                outline="",
            )

            self._stars.append(
                (item, x, y, radius, index * 0.73)
            )

        # Technical corner brackets.
        for x, y, dx, dy in (
            (85, 60, 1, 1),
            (715, 60, -1, 1),
            (85, 460, 1, -1),
            (715, 460, -1, -1),
        ):
            self._line(
                x, y + dy * 20,
                x, y,
                x + dx * 20, y,
                fill="#284559",
                width=1.5,
            )

        self._text(
            110, 63,
            "ENFOQUE / FOCUS INTERFACE",
            10,
            self.MUTED,
            anchor="w",
        )

        self._text(
            690, 63,
            "PROTOCOL 03",
            10,
            self.MUTED,
            anchor="e",
        )

        # Layered halo.
        for radius, color in (
            (112, "#0A1220"),
            (98, "#0B1625"),
            (83, "#0C1B2B"),
            (65, "#0D2130"),
        ):
            canvas.create_oval(
                *self._xy(
                    400 - radius,
                    190 - radius,
                    400 + radius,
                    190 + radius,
                ),
                fill=color,
                outline="",
            )

        canvas.create_oval(
            *self._xy(315, 105, 485, 275),
            outline="#193346",
            width=max(1, self._scale),
        )

        # Radial HUD markers.
        for index in range(48):
            angle = math.tau * index / 48
            inner = 103 if index % 4 == 0 else 107
            outer = 113

            self._line(
                400 + math.cos(angle) * inner,
                190 + math.sin(angle) * inner,
                400 + math.cos(angle) * outer,
                190 + math.sin(angle) * outer,
                fill=(
                    "#315569"
                    if index % 4 == 0
                    else "#172D40"
                ),
            )

        self._rings = []

        for radius, extent, color, width in (
            (94, 112, self.CYAN, 2.5),
            (80, 82, self.PURPLE, 2),
            (69, 48, "#5B9DB8", 1.5),
        ):
            item = canvas.create_arc(
                *self._xy(
                    400 - radius,
                    190 - radius,
                    400 + radius,
                    190 + radius,
                ),
                start=0,
                extent=extent,
                style=tk.ARC,
                outline=color,
                width=max(1, width * self._scale),
            )
            self._rings.append(item)

        self._core = canvas.create_polygon(
            *self._xy(
                400, 153,
                432, 190,
                400, 227,
                368, 190,
            ),
            fill="#102C3B",
            outline=self.CYAN,
            width=max(1, 2 * self._scale),
        )

        self._line(
            385, 190,
            397, 202,
            418, 177,
            fill=self.WHITE,
            width=3,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )

        self._title = self._text(
            400, 330,
            "ENFOQUE-AI",
            47,
            self.WHITE,
            weight="bold",
        )

        self._subtitle = self._text(
            400, 365,
            "LESS NOISE.  MORE FOCUS.",
            11,
            self.MUTED,
        )

        # Progress rail.
        self._line(
            190, 407,
            610, 407,
            fill="#14283B",
            width=5,
            capstyle=tk.ROUND,
        )

        self._bar_glow = self._line(
            190, 407,
            190, 407,
            fill="#123E50",
            width=11,
            capstyle=tk.ROUND,
            state="hidden",
        )

        self._bar = self._line(
            190, 407,
            190, 407,
            fill=self.CYAN,
            width=3,
            capstyle=tk.ROUND,
            state="hidden",
        )

        self._bar_tip = canvas.create_oval(
            *self._xy(187, 404, 193, 410),
            fill=self.WHITE,
            outline="",
            state="hidden",
        )

        self._status = self._text(
            190, 433,
            "Preparing your workspace",
            11,
            self.MUTED,
            anchor="w",
        )

        self._counter = self._text(
            610, 433,
            "000%",
            12,
            self.CYAN,
            anchor="e",
        )

        self._text(
            400, 488,
            "D E E P   W O R K   S T A R T S   H E R E",
            9,
            "#40566F",
        )

    def _animate(self):
        self._job = None

        if self._closed:
            return

        frame_started = time.perf_counter()

        if self._size is None:
            self._job = self.after(
                self.FRAME_MS,
                self._animate,
            )
            return

        if self._started is None:
            self._started = frame_started

        elapsed = frame_started - self._started
        progress = self._smooth(elapsed / self.duration)

        exit_start = self.duration + 0.30
        exit_progress = self._clamp(
            (elapsed - exit_start) / self.EXIT_SECONDS
        )

        if exit_progress >= 1.0:
            self.destroy()
            return

        canvas = self.canvas
        entrance = self._smooth(elapsed / 0.65)
        pulse = 0.5 + 0.5 * math.sin(elapsed * 2.8)

        # Ambient drift and gentle twinkling.
        for item, x, y, radius, phase in self._stars:
            drift_x = math.sin(elapsed * 0.22 + phase) * 5
            drift_y = math.cos(elapsed * 0.18 + phase) * 4

            brightness = 0.25 + 0.45 * (
                0.5 + 0.5 * math.sin(elapsed * 1.1 + phase)
            )

            canvas.coords(
                item,
                *self._xy(
                    x + drift_x - radius,
                    y + drift_y - radius,
                    x + drift_x + radius,
                    y + drift_y + radius,
                ),
            )

            canvas.itemconfigure(
                item,
                fill=self._mix(
                    self.BG,
                    "#6CA0BA",
                    brightness,
                ),
            )

        # Time-based rotation remains consistent if a frame is delayed.
        for item, speed, offset in zip(
            self._rings,
            (48, -64, 85),
            (0, 145, 260),
        ):
            canvas.itemconfigure(
                item,
                start=(elapsed * speed + offset) % 360,
            )

        canvas.itemconfigure(
            self._core,
            fill=self._mix(
                "#102333",
                "#15465A",
                pulse * 0.65,
            ),
            outline=self._mix(
                "#3899B0",
                self.CYAN,
                pulse,
            ),
        )

        canvas.coords(
            self._title,
            *self._xy(
                400,
                330 + 12 * (1 - entrance),
            ),
        )

        canvas.itemconfigure(
            self._title,
            fill=self._mix(
                self.BG,
                self.WHITE,
                entrance,
            ),
        )

        canvas.itemconfigure(
            self._subtitle,
            fill=self._mix(
                self.BG,
                self.MUTED,
                entrance,
            ),
        )

        tip_x = 190 + 420 * progress

        bar_color = self._mix(
            self.CYAN,
            self.PURPLE,
            progress * 0.55,
        )

        if progress > 0:
            for item in (
                self._bar_glow,
                self._bar,
                self._bar_tip,
            ):
                canvas.itemconfigure(item, state="normal")

        for item in (self._bar_glow, self._bar):
            canvas.coords(
                item,
                *self._xy(
                    190, 407,
                    tip_x, 407,
                ),
            )

        canvas.itemconfigure(
            self._bar,
            fill=bar_color,
        )

        canvas.coords(
            self._bar_tip,
            *self._xy(
                tip_x - 3, 404,
                tip_x + 3, 410,
            ),
        )

        canvas.itemconfigure(
            self._counter,
            text=f"{int(progress * 100):03d}%",
            fill=bar_color,
        )

        if progress < 0.30:
            status = "Preparing your workspace"
        elif progress < 0.65:
            status = "Bringing everything into focus"
        elif progress < 1.0:
            status = "Almost there"
        else:
            status = "Your workspace is ready"

        canvas.itemconfigure(
            self._status,
            text=status,
            fill=(
                "#86EFAC"
                if progress >= 1.0
                else self.MUTED
            ),
        )

        # Reveal the existing app without changing window opacity.
        if exit_progress > 0:
            self.place_configure(
                rely=-self._ease_out_cubic(exit_progress)
            )

        spent_ms = (
            time.perf_counter() - frame_started
        ) * 1000

        delay = max(
            1,
            round(self.FRAME_MS - spent_ms),
        )

        self._job = self.after(delay, self._animate)

    def _cancel_animation(self):
        self._closed = True

        if self._job is not None:
            job = self._job
            self._job = None

            try:
                self.after_cancel(job)
            except tk.TclError:
                # Expected if Tcl is already shutting down.
                pass

    def _on_destroy(self, event):
        if event.widget is self:
            self._cancel_animation()

    def destroy(self):
        self._cancel_animation()
        super().destroy()


# ------------------ MAIN APPLICATION ------------------

class NexusLockdownSuite(ctk.CTk):
    def __init__(self, with_splash=False):
        super().__init__()

        self.title("ENFOQUE-AI - LOCKDOWN SUITE")
        self.geometry("1200x780")
        self.minsize(700, 500)
        self.configure(fg_color=BG_DARK)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_sidebar()

        self.container = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.container.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=20,
            pady=20,
        )
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.pages = {}

        for page_class in (
            LockdownDashboardPage,
            AIAssistantPage,
        ):
            page = page_class(
                parent=self.container,
                controller=self,
            )
            self.pages[page_class.__name__] = page
            page.grid(row=0, column=0, sticky="nsew")

        self.show_page("LockdownDashboardPage")

        self.splash = None

        if with_splash:
            self.splash = LoadingSplash(
                self,
                duration=SPLASH_DURATION,
            )

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color=BG_DARK,
        )
        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        ctk.CTkLabel(
            self.sidebar,
            text="ENFOQUE-AI",
            font=("Consolas", 26, "bold"),
            text_color=ACCENT_CYAN,
        ).pack(pady=(30, 5), padx=20)

        ctk.CTkLabel(
            self.sidebar,
            text="LOCKDOWN PROTOCOL v3.0",
            font=("Consolas", 9),
            text_color=ACCENT_RED,
        ).pack(pady=(0, 20))

        for label, page_name in (
            ("Command Center", "LockdownDashboardPage"),
            ("AI Assistant & Planner", "AIAssistantPage"),
        ):
            ctk.CTkButton(
                self.sidebar,
                text=label,
                fg_color=CARD_BG,
                hover_color=ACCENT_CYAN,
                text_color=TEXT_LIGHT,
                font=("Helvetica", 13, "bold"),
                command=lambda name=page_name: self.show_page(name),
            ).pack(
                pady=8,
                padx=20,
                fill="x",
            )

        lock_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color=CARD_BG,
            corner_radius=12,
            border_color=ACCENT_RED,
            border_width=1,
        )
        lock_frame.pack(
            side="bottom",
            pady=20,
            padx=15,
            fill="x",
        )

        ctk.CTkLabel(
            lock_frame,
            text="HARDCORE LOCK",
            text_color=ACCENT_RED,
            font=("Consolas", 11, "bold"),
        ).pack(pady=(10, 2))

        self.lock_switch = ctk.CTkSwitch(
            lock_frame,
            text="Always on Top",
            text_color=TEXT_LIGHT,
            command=self.toggle_lockdown,
            progress_color=ACCENT_RED,
        )
        self.lock_switch.pack(
            pady=(5, 12),
            padx=10,
        )

    def toggle_lockdown(self):
        self.attributes(
            "-topmost",
            bool(self.lock_switch.get()),
        )

    def show_page(self, page_name):
        self.pages[page_name].tkraise()

    def _on_close(self):
        for page in self.pages.values():
            page.shutdown()

        self.destroy()


# ------------------ PAGE 1: LOCKDOWN DASHBOARD ------------------

class LockdownDashboardPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(
            parent,
            fg_color="transparent",
        )

        self.controller = controller
        self.grid_columnconfigure(0, weight=1)

        self.current_user = "Soap"
        self.total_points = 0
        self.focus_minutes = 0.0
        self.task_widgets = []

        self.time_left = 25 * 60
        self.timer_running = False
        self.timer_job = None

        self._closed = False
        self._api_events = queue.Queue()
        self._fetching = False
        self._refresh_pending = False
        self._refresh_job = None
        self._poll_job = None

        # Serialize score writes so rapid checkbox changes cannot
        # send an older score after a newer score.
        self._score_updates = queue.Queue()
        self._score_worker = threading.Thread(
            target=self._score_worker_loop,
            daemon=True,
            name="ScoreUpdateWorker",
        )
        self._score_worker.start()

        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        scroll.pack(fill="both", expand=True)

        self._build_banner(scroll)
        self._build_username_card(scroll)
        self._build_timer_card(scroll)
        self._build_task_card(scroll)
        self._build_leaderboard_card(scroll)

        self._poll_job = self.after(
            100,
            self._poll_api_events,
        )
        self._refresh_job = self.after(
            500,
            self._scheduled_refresh,
        )

    def _make_card(self, parent, border=CARD_BORDER):
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            corner_radius=14,
            border_color=border,
            border_width=1,
        )
        card.pack(fill="x", pady=10)
        return card

    def _build_banner(self, parent):
        banner = self._make_card(parent, ACCENT_RED)

        ctk.CTkLabel(
            banner,
            text="SQUAD DIRECTIVE: NO DISTRACTIONS ALLOWED",
            font=("Consolas", 11, "bold"),
            text_color=ACCENT_RED,
        ).pack(
            anchor="w",
            pady=(15, 5),
            padx=20,
        )

        ctk.CTkLabel(
            banner,
            text=(
                '"Lock in right now. Every line of code written today '
                'secures the hackathon victory tomorrow."'
            ),
            font=("Helvetica", 14, "italic"),
            text_color=TEXT_LIGHT,
            wraplength=750,
            justify="left",
            anchor="w",
        ).pack(
            anchor="w",
            fill="x",
            pady=(0, 15),
            padx=20,
        )

    def _build_username_card(self, parent):
        card = self._make_card(parent)

        ctk.CTkLabel(
            card,
            text="YOUR CALLSIGN",
            font=("Consolas", 12, "bold"),
            text_color=ACCENT_CYAN,
        ).pack(
            anchor="w",
            pady=(15, 5),
            padx=20,
        )

        row = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        row.pack(
            fill="x",
            padx=20,
            pady=(0, 8),
        )

        self.username_entry = ctk.CTkEntry(
            row,
            placeholder_text="Enter your name",
            font=("Helvetica", 13),
            fg_color="#1E293B",
            text_color=TEXT_LIGHT,
            width=260,
        )
        self.username_entry.insert(0, self.current_user)
        self.username_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10),
        )

        ctk.CTkButton(
            row,
            text="Set Name",
            fg_color=ACCENT_CYAN,
            text_color="black",
            font=("Helvetica", 12, "bold"),
            width=100,
            command=self._set_username,
        ).pack(side="left")

        self.username_status = ctk.CTkLabel(
            card,
            text="",
            font=("Consolas", 11),
            text_color=ACCENT_GREEN,
            anchor="w",
            wraplength=650,
        )
        self.username_status.pack(
            fill="x",
            padx=20,
            pady=(0, 10),
        )

    def _build_timer_card(self, parent):
        card = self._make_card(parent)

        ctk.CTkLabel(
            card,
            text="LOCKDOWN SPRINT TIMER",
            font=("Consolas", 12, "bold"),
            text_color=ACCENT_CYAN,
        ).pack(
            anchor="w",
            pady=(15, 5),
            padx=20,
        )

        self.timer_display = ctk.CTkLabel(
            card,
            text="25:00",
            font=("Consolas", 48, "bold"),
            text_color=TEXT_LIGHT,
        )
        self.timer_display.pack(pady=5)

        buttons = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        buttons.pack(pady=(0, 15))

        self.btn_start = ctk.CTkButton(
            buttons,
            text="Start Locking In",
            fg_color=ACCENT_CYAN,
            text_color="black",
            font=("Helvetica", 12, "bold"),
            width=150,
            command=self.toggle_timer,
        )
        self.btn_start.pack(side="left", padx=5)

        ctk.CTkButton(
            buttons,
            text="Reset",
            fg_color="#374151",
            text_color=TEXT_LIGHT,
            font=("Helvetica", 12, "bold"),
            width=80,
            command=self.reset_timer,
        ).pack(side="left", padx=5)

    def _build_task_card(self, parent):
        card = self._make_card(parent)

        header = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        header.pack(
            fill="x",
            padx=20,
            pady=(15, 5),
        )

        ctk.CTkLabel(
            header,
            text="DAILY TASKS",
            font=("Consolas", 12, "bold"),
            text_color=ACCENT_PURPLE,
        ).pack(side="left")

        self.points_badge = ctk.CTkLabel(
            header,
            text=f"⚡ {self.total_points} pts",
            font=("Consolas", 12, "bold"),
            text_color=ACCENT_GREEN,
        )
        self.points_badge.pack(side="right")

        add_row = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        add_row.pack(
            fill="x",
            padx=20,
            pady=(5, 10),
        )

        self.task_entry = ctk.CTkEntry(
            add_row,
            placeholder_text="Add a task (e.g. Finish login module)...",
            font=("Helvetica", 13),
            fg_color="#1E293B",
            text_color=TEXT_LIGHT,
        )
        self.task_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10),
        )
        self.task_entry.bind(
            "<Return>",
            lambda event: self.add_task(),
        )

        ctk.CTkButton(
            add_row,
            text="+ Add",
            fg_color=ACCENT_PURPLE,
            text_color=TEXT_LIGHT,
            font=("Helvetica", 12, "bold"),
            width=80,
            command=self.add_task,
        ).pack(side="left")

        self.task_list_frame = ctk.CTkScrollableFrame(
            card,
            fg_color="#0F172A",
            height=180,
        )
        self.task_list_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 15),
        )

        self.empty_label = ctk.CTkLabel(
            self.task_list_frame,
            text="No tasks yet. Add one above ↑",
            font=("Helvetica", 12),
            text_color=TEXT_MUTED,
        )
        self.empty_label.pack(pady=20)

    def _build_leaderboard_card(self, parent):
        card = self._make_card(parent)

        header = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        header.pack(
            fill="x",
            padx=20,
            pady=(15, 10),
        )

        ctk.CTkLabel(
            header,
            text="🏆 SQUAD RANKINGS",
            font=("Consolas", 12, "bold"),
            text_color=TEXT_LIGHT,
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="↻ Refresh",
            fg_color="#374151",
            text_color=TEXT_LIGHT,
            font=("Helvetica", 11),
            width=80,
            command=self.refresh_leaderboard,
        ).pack(side="right")

        self.lb_status = ctk.CTkLabel(
            card,
            text="Loading...",
            font=("Consolas", 10),
            text_color=TEXT_MUTED,
            wraplength=650,
            justify="left",
        )
        self.lb_status.pack(anchor="w", padx=20)

        self.lb_rows_frame = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        self.lb_rows_frame.pack(
            fill="x",
            padx=15,
            pady=(5, 15),
        )

    # ------------------ Username ------------------

    def _set_username(self):
        name = self.username_entry.get().strip()

        if not name:
            self.username_status.configure(
                text="Please enter a name.",
                text_color=ACCENT_RED,
            )
            return

        self.current_user = name

        self.username_status.configure(
            text=f"✓ Set to '{name}'",
            text_color=ACCENT_GREEN,
        )

        self._push_score()

    # ------------------ Timer ------------------

    def toggle_timer(self):
        if self.timer_running:
            self.timer_running = False
            self._cancel_timer()

            self.btn_start.configure(
                text="Resume",
                fg_color=ACCENT_CYAN,
            )
            self._push_score()
            return

        if self.time_left <= 0:
            self.reset_timer()

        self.timer_running = True
        self._timer_last_tick = time.perf_counter()

        self.btn_start.configure(
            text="Pause",
            fg_color=ACCENT_RED,
        )

        self.timer_job = self.after(
            100,
            self.run_timer,
        )

    def run_timer(self):
        self.timer_job = None

        if not self.timer_running or self._closed:
            return

        now = time.perf_counter()
        elapsed = now - self._timer_last_tick
        self._timer_last_tick = now

        consumed = min(elapsed, self.time_left)
        self.time_left = max(0.0, self.time_left - elapsed)
        self.focus_minutes += consumed / 60.0

        remaining = math.ceil(self.time_left)
        minutes, seconds = divmod(remaining, 60)

        self.timer_display.configure(
            text=f"{minutes:02d}:{seconds:02d}"
        )

        if self.time_left > 0:
            self.timer_job = self.after(
                100,
                self.run_timer,
            )
        else:
            self.timer_running = False

            self.timer_display.configure(
                text="SESSION COMPLETE!",
                font=("Consolas", 30, "bold"),
            )
            self.btn_start.configure(
                text="Start Again",
                fg_color=ACCENT_CYAN,
            )

            self._push_score()

    def _cancel_timer(self):
        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None

    def reset_timer(self):
        self.timer_running = False
        self._cancel_timer()

        self.time_left = 25 * 60

        self.timer_display.configure(
            text="25:00",
            font=("Consolas", 48, "bold"),
        )
        self.btn_start.configure(
            text="Start Locking In",
            fg_color=ACCENT_CYAN,
        )

    # ------------------ Tasks ------------------

    def add_task(self):
        text = self.task_entry.get().strip()

        if not text:
            return

        self.task_entry.delete(0, "end")
        self.empty_label.pack_forget()

        row = ctk.CTkFrame(
            self.task_list_frame,
            fg_color="#1E293B",
            corner_radius=8,
        )
        row.pack(
            fill="x",
            pady=4,
            padx=4,
        )

        done_var = ctk.BooleanVar(value=False)

        checkbox = ctk.CTkCheckBox(
            row,
            text=text,
            variable=done_var,
            font=("Helvetica", 13),
            text_color=TEXT_LIGHT,
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_CYAN,
            checkmark_color="black",
            command=lambda: self._on_task_toggled(
                done_var,
                row,
            ),
        )
        checkbox.pack(
            side="left",
            padx=15,
            pady=10,
        )

        ctk.CTkButton(
            row,
            text="✕",
            width=30,
            height=28,
            fg_color="transparent",
            text_color=TEXT_MUTED,
            hover_color=ACCENT_RED,
            font=("Helvetica", 12),
            command=lambda: self._delete_task(
                row,
                done_var,
            ),
        ).pack(
            side="right",
            padx=10,
        )

        self.task_widgets.append(
            (text, done_var, row)
        )

    def _on_task_toggled(self, done_var, row):
        if done_var.get():
            self.total_points += 1
            row.configure(fg_color="#14532D")
        else:
            self.total_points = max(
                0,
                self.total_points - 1,
            )
            row.configure(fg_color="#1E293B")

        self.points_badge.configure(
            text=f"⚡ {self.total_points} pts"
        )

        self._push_score()

    def _delete_task(self, row, done_var):
        if done_var.get():
            self.total_points = max(
                0,
                self.total_points - 1,
            )

            self.points_badge.configure(
                text=f"⚡ {self.total_points} pts"
            )

            self._push_score()

        self.task_widgets = [
            (text, variable, frame)
            for text, variable, frame in self.task_widgets
            if frame is not row
        ]

        row.destroy()

        if not self.task_widgets:
            self.empty_label.pack(pady=20)

    # ------------------ Thread-safe API handling ------------------

    def _push_score(self):
        self._score_updates.put((
            self.current_user,
            self.total_points,
            round(self.focus_minutes / 60, 2),
        ))

    def _score_worker_loop(self):
        """Worker thread: network and queues only; no Tk calls."""
        while True:
            update = self._score_updates.get()

            if update is None:
                return

            success, error = api_update_score(*update)

            self._api_events.put((
                "score",
                success,
                error,
            ))

    def _scheduled_refresh(self):
        self._refresh_job = None
        self.refresh_leaderboard()

    def refresh_leaderboard(self):
        if self._closed:
            return

        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

        if self._fetching:
            self._refresh_pending = True
            return

        self._fetching = True

        self.lb_status.configure(
            text="Refreshing leaderboard...",
            text_color=TEXT_MUTED,
        )

        threading.Thread(
            target=self._fetch_leaderboard_worker,
            daemon=True,
            name="LeaderboardFetchWorker",
        ).start()

    def _fetch_leaderboard_worker(self):
        data, error = api_get_leaderboard()

        self._api_events.put((
            "leaderboard",
            data,
            error,
        ))

    def _poll_api_events(self):
        self._poll_job = None

        if self._closed:
            return

        # Bound work per callback to keep animations responsive.
        for _ in range(50):
            try:
                event = self._api_events.get_nowait()
            except queue.Empty:
                break

            kind = event[0]

            if kind == "leaderboard":
                _, data, error = event
                self._fetching = False

                self._render_leaderboard(data, error)

                if self._refresh_pending:
                    self._refresh_pending = False
                    self.refresh_leaderboard()
                elif self._refresh_job is None:
                    self._refresh_job = self.after(
                        15000,
                        self._scheduled_refresh,
                    )

            elif kind == "score":
                _, success, error = event

                if success:
                    self.refresh_leaderboard()
                else:
                    self.lb_status.configure(
                        text=f"Score sync failed: {error}",
                        text_color=ACCENT_RED,
                    )

        self._poll_job = self.after(
            50,
            self._poll_api_events,
        )

    def _render_leaderboard(self, data, error=None):
        if error:
            # Preserve existing rows if a refresh fails.
            self.lb_status.configure(
                text=f"Leaderboard unavailable: {error}",
                text_color=ACCENT_RED,
            )
            return

        for widget in self.lb_rows_frame.winfo_children():
            widget.destroy()

        if not data:
            self.lb_status.configure(
                text="No scores yet — complete a task to appear here!",
                text_color=TEXT_MUTED,
            )
            return

        self.lb_status.configure(
            text=(
                "Last updated: "
                f"{datetime.now().strftime('%H:%M:%S')}"
            ),
            text_color=TEXT_MUTED,
        )

        medals = ["🥇", "🥈", "🥉"]

        for index, entry in enumerate(data):
            if not isinstance(entry, dict):
                continue

            name = str(entry.get("username", "Unknown"))
            points = entry.get("points", 0)

            try:
                hours = float(entry.get("focus_hours", 0.0))
            except (ValueError, TypeError):
                hours = 0.0

            is_you = (
                name.casefold()
                == self.current_user.casefold()
            )

            rank = (
                medals[index]
                if index < 3
                else f"#{index + 1}"
            )

            row = ctk.CTkFrame(
                self.lb_rows_frame,
                fg_color=(
                    "#1F2937"
                    if is_you
                    else "transparent"
                ),
                corner_radius=8,
            )
            row.pack(fill="x", pady=4)

            ctk.CTkLabel(
                row,
                text=(
                    f"{rank}  {name}"
                    f"{' (You)' if is_you else ''}"
                ),
                font=("Consolas", 13, "bold"),
                text_color=(
                    ACCENT_CYAN
                    if is_you
                    else TEXT_LIGHT
                ),
            ).pack(
                side="left",
                padx=15,
                pady=10,
            )

            ctk.CTkLabel(
                row,
                text=f"⚡ {points} pts  |  🕐 {hours:.1f}h",
                font=("Helvetica", 11),
                text_color=(
                    ACCENT_GREEN
                    if is_you
                    else TEXT_MUTED
                ),
            ).pack(
                side="right",
                padx=15,
                pady=10,
            )

    def shutdown(self):
        self._closed = True
        self.timer_running = False
        self._cancel_timer()

        for attribute in ("_poll_job", "_refresh_job"):
            job = getattr(self, attribute)

            if job is not None:
                self.after_cancel(job)
                setattr(self, attribute, None)

        self._score_updates.put(None)


# ------------------ PAGE 2: AI ASSISTANT & PLANNER ------------------

class AIAssistantPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(
            parent,
            fg_color="transparent",
        )

        self.controller = controller
        self.grid_columnconfigure(0, weight=1)

        self.chat_history = []
        self._closed = False

        self._mic_stop_event = threading.Event()
        self._mic_events = queue.Queue()
        self._is_recording = False
        self._poll_job = None

        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        scroll.pack(fill="both", expand=True)

        self._build_title_card(scroll)
        self._build_input_card(scroll)
        self._build_history_card(scroll)
        self._build_output_card(scroll)

        self._poll_job = self.after(
            100,
            self._poll_mic_events,
        )

    def _make_card(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=CARD_BG,
            corner_radius=12,
            border_color=CARD_BORDER,
            border_width=1,
        )
        card.pack(fill="x", pady=10)
        return card

    def _build_title_card(self, parent):
        card = self._make_card(parent)

        ctk.CTkLabel(
            card,
            text="AI Schedule Assistant & Planner",
            font=("Helvetica", 18, "bold"),
            text_color=ACCENT_CYAN,
            wraplength=780,
            justify="left",
            anchor="w",
        ).pack(
            fill="x",
            pady=(15, 10),
            padx=20,
        )

        ctk.CTkLabel(
            card,
            text=(
                "Talk or type to create daily schedules, weekly planners, "
                "and task prioritization plans.\n"
                "Planning currently uses built-in templates."
            ),
            font=("Helvetica", 13),
            text_color=TEXT_MUTED,
            wraplength=780,
            justify="left",
            anchor="w",
        ).pack(
            fill="x",
            padx=20,
            pady=(0, 15),
        )

    def _build_input_card(self, parent):
        card = self._make_card(parent)

        controls = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        controls.pack(
            fill="x",
            padx=20,
            pady=(15, 5),
        )

        self.mic_button = ctk.CTkButton(
            controls,
            text="🎤 Speak",
            fg_color="#374151",
            hover_color=ACCENT_RED,
            text_color=TEXT_LIGHT,
            font=("Helvetica", 12, "bold"),
            width=120,
            command=self.toggle_microphone,
        )
        self.mic_button.pack(
            side="left",
            padx=(0, 10),
        )

        self.energy_bar = ctk.CTkProgressBar(
            controls,
            width=140,
            height=14,
            progress_color=ACCENT_GREEN,
            fg_color="#1E293B",
            corner_radius=4,
        )
        self.energy_bar.set(0)
        self.energy_bar.pack(
            side="left",
            padx=(10, 5),
        )

        self.energy_label = ctk.CTkLabel(
            controls,
            text="",
            font=("Consolas", 10),
            text_color=TEXT_MUTED,
        )
        self.energy_label.pack(
            side="left",
            padx=(0, 5),
        )

        self.mic_status_label = ctk.CTkLabel(
            card,
            text="Microphone: Ready",
            font=("Consolas", 11),
            text_color=TEXT_MUTED,
            wraplength=650,
            justify="left",
            anchor="w",
        )
        self.mic_status_label.pack(
            fill="x",
            padx=20,
            pady=(0, 5),
        )

        ctk.CTkLabel(
            card,
            text="What would you like to plan?",
            font=("Helvetica", 14, "bold"),
            text_color=TEXT_LIGHT,
        ).pack(
            anchor="w",
            pady=(10, 5),
            padx=20,
        )

        self.query_entry = ctk.CTkTextbox(
            card,
            height=80,
            font=("Helvetica", 13),
            fg_color="#1E293B",
            text_color=TEXT_LIGHT,
        )
        self.query_entry.pack(
            fill="x",
            padx=20,
            pady=10,
        )
        self.query_entry.insert(
            "1.0",
            "e.g., Create a daily schedule for a productive workday...",
        )

        self.gen_btn = ctk.CTkButton(
            card,
            text="✨ Generate Plan",
            fg_color=ACCENT_CYAN,
            text_color="black",
            font=("Helvetica", 14, "bold"),
            hover_color=ACCENT_PURPLE,
            width=160,
            command=self.generate_plan,
        )
        self.gen_btn.pack(
            anchor="w",
            padx=20,
            pady=(5, 10),
        )

        quick_frame = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        quick_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 15),
        )

        quick_actions = [
            ("Daily Schedule", "Create my daily schedule"),
            ("Weekly Planner", "Make a weekly plan"),
            ("Task Priority", "Prioritize my tasks"),
        ]

        for label, query in quick_actions:
            ctk.CTkButton(
                quick_frame,
                text=label,
                fg_color="#374151",
                text_color=TEXT_LIGHT,
                font=("Helvetica", 11),
                width=110,
                command=lambda value=query: self.quick_action(value),
            ).pack(
                side="left",
                padx=(0, 8),
            )

    def _build_history_card(self, parent):
        card = self._make_card(parent)

        ctk.CTkLabel(
            card,
            text="💬 Conversation History",
            font=("Helvetica", 16, "bold"),
            text_color=ACCENT_PURPLE,
            anchor="w",
        ).pack(
            fill="x",
            pady=(15, 10),
            padx=20,
        )

        self.history_frame = ctk.CTkScrollableFrame(
            card,
            fg_color="#0F172A",
            height=200,
        )
        self.history_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 15),
        )

    def _build_output_card(self, parent):
        self.result_card = self._make_card(parent)

        ctk.CTkLabel(
            self.result_card,
            text="📅 Generated Schedule & Plan",
            font=("Helvetica", 16, "bold"),
            text_color=ACCENT_CYAN,
            anchor="w",
        ).pack(
            fill="x",
            pady=(15, 10),
            padx=20,
        )

        self.plan_output = ctk.CTkLabel(
            self.result_card,
            text="Your schedule will appear here after generation.",
            font=("Consolas", 13),
            text_color=TEXT_LIGHT,
            justify="left",
            anchor="nw",
            wraplength=780,
        )
        self.plan_output.pack(
            fill="x",
            expand=True,
            pady=(0, 20),
            padx=20,
        )

        # Keep output readable when the app is resized.
        self.result_card.bind(
            "<Configure>",
            self._resize_output,
            add="+",
        )

    def _resize_output(self, event):
        self.plan_output.configure(
            wraplength=max(200, event.width - 45)
        )

    # ------------------ Voice input ------------------

    def toggle_microphone(self):
        if self._is_recording:
            if self._mic_stop_event.is_set():
                return

            self._mic_stop_event.set()

            self.mic_button.configure(
                text="⏳ Processing...",
                fg_color=CARD_BG,
                state="disabled",
            )
            self.mic_status_label.configure(
                text="Microphone: PROCESSING",
                text_color=ACCENT_CYAN,
            )
            self.plan_output.configure(
                text="🔄 Transcribing speech..."
            )
            return

        self._is_recording = True
        self._mic_stop_event.clear()

        self.mic_button.configure(
            text="⏹ Stop & Send",
            fg_color=ACCENT_RED,
            hover_color="#BE123C",
            state="normal",
        )
        self.mic_status_label.configure(
            text="Microphone: STARTING...",
            text_color=ACCENT_RED,
        )
        self.plan_output.configure(
            text=(
                "🎙 Microphone active...\n"
                "Speak your request, then click 'Stop & Send', "
                "or pause for a moment."
            )
        )

        self.start_voice_recording()

    def start_voice_recording(self):
        threading.Thread(
            target=self._listen_worker,
            daemon=True,
            name="SpeechRecognitionThread",
        ).start()

    def _listen_worker(self):
        """Worker thread: never touches Tk widgets."""
        emit = self._mic_events.put

        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            recognizer.operation_timeout = 15

            with sr.Microphone(
                device_index=MIC_DEVICE_INDEX
            ) as source:
                rate = source.SAMPLE_RATE
                width = source.SAMPLE_WIDTH

                if width != 2:
                    raise ValueError(
                        "Voice capture requires 16-bit microphone audio."
                    )

                audio_bytes, spoke, reason = capture_audio(
                    lambda count: source.stream.read(count),
                    rate,
                    source.CHUNK,
                    self._mic_stop_event,
                    emit,
                )

            if reason == "timeout" and not spoke:
                emit((
                    "error",
                    "No speech detected. Check your microphone "
                    "selection and speak clearly.",
                ))
                return

            if len(audio_bytes) < int(rate * width * 0.4):
                emit((
                    "error",
                    "I barely heard anything. Click Speak, talk, "
                    "then click Stop & Send.",
                ))
                return

            emit((
                "status",
                "Microphone: TRANSCRIBING...",
            ))

            text = recognizer.recognize_google(
                sr.AudioData(audio_bytes, rate, width),
                language=SPEECH_LANGUAGE,
            )

            emit(("text", text))

        except ImportError as exc:
            emit((
                "error",
                f"Voice input dependencies are missing ({exc}). "
                "Install SpeechRecognition and PyAudio. "
                "On Python versions that require it, install audioop-lts.",
            ))

        except Exception as exc:
            name = type(exc).__name__
            message = str(exc)

            if name == "UnknownValueError":
                error = (
                    "I couldn't understand that. Speak closer to the "
                    "microphone or reduce background noise."
                )
            elif name == "RequestError":
                error = (
                    "Speech service unavailable; an internet connection "
                    f"is required. Details: {message}"
                )
            elif "audioop" in message.lower():
                error = (
                    "Missing audio module for this Python version. "
                    "Install audioop-lts."
                )
            else:
                error = f"Microphone error: {name}: {message}"

            emit(("error", error))

        finally:
            emit(("done",))

    def _poll_mic_events(self):
        self._poll_job = None

        if self._closed:
            return

        last_level = None

        # Limit processing per callback to protect UI responsiveness.
        for _ in range(200):
            try:
                event = self._mic_events.get_nowait()
            except queue.Empty:
                break

            if event[0] == "level":
                last_level = event
            else:
                self._handle_mic_event(event)

        if (
            last_level is not None
            and self._is_recording
            and not self._mic_stop_event.is_set()
        ):
            self._update_energy_bar(
                last_level[1],
                last_level[2],
            )

        self._poll_job = self.after(
            50,
            self._poll_mic_events,
        )

    def _handle_mic_event(self, event):
        kind = event[0]

        if kind == "ready":
            self.mic_status_label.configure(
                text=(
                    "Microphone: LISTENING "
                    "(Speak now, then click Stop & Send)"
                ),
                text_color=ACCENT_RED,
            )

        elif kind == "status":
            self.mic_status_label.configure(
                text=event[1],
                text_color=ACCENT_CYAN,
            )

        elif kind == "text":
            self._on_speech_recognized(event[1])

        elif kind == "error":
            self._on_speech_error(event[1])

        elif kind == "done":
            self._finish_recording()

    def _finish_recording(self):
        self._is_recording = False
        self._mic_stop_event.clear()

        self.mic_button.configure(
            text="🎤 Speak",
            fg_color="#374151",
            hover_color=ACCENT_RED,
            state="normal",
        )

        self._reset_energy_bar()

    def _update_energy_bar(self, level, threshold):
        ratio = (
            min(level / (threshold * 2.5), 1.0)
            if threshold > 0
            else 0.0
        )

        self.energy_bar.set(ratio)

        if ratio < 0.25:
            color = TEXT_MUTED
        elif ratio < 0.6:
            color = ACCENT_GREEN
        elif ratio < 0.85:
            color = ACCENT_CYAN
        else:
            color = ACCENT_RED

        self.energy_bar.configure(
            progress_color=color
        )
        self.energy_label.configure(
            text=f"{int(ratio * 100)}%",
            text_color=color,
        )

    def _reset_energy_bar(self):
        self.energy_bar.set(0)
        self.energy_bar.configure(
            progress_color=ACCENT_GREEN
        )
        self.energy_label.configure(
            text="",
            text_color=TEXT_MUTED,
        )

    def _on_speech_recognized(self, text):
        self.mic_status_label.configure(
            text="Microphone: Ready",
            text_color=TEXT_MUTED,
        )

        self.query_entry.delete("1.0", "end")
        self.query_entry.insert("1.0", text)

        self.plan_output.configure(
            text=(
                f'✅ Successfully transcribed voice:\n"{text}"\n\n'
                "Edit the text if needed, then click Generate Plan."
            )
        )

    def _on_speech_error(self, error):
        self.mic_status_label.configure(
            text="Microphone: ERROR",
            text_color=ACCENT_RED,
        )
        self.plan_output.configure(
            text=(
                f"⚠ {error}\n\n"
                "You can still type your request above."
            )
        )

    def stop_voice_recording(self):
        if self._is_recording:
            self._mic_stop_event.set()

    # ------------------ Planner ------------------

    def quick_action(self, query):
        self.query_entry.delete("1.0", "end")
        self.query_entry.insert("1.0", query)

    def generate_plan(self):
        query = self.query_entry.get(
            "1.0",
            "end",
        ).strip()

        if not query or query.startswith("e.g.,"):
            self.plan_output.configure(
                text="⚠ Please enter your planning request first!"
            )
            return

        self.add_to_history("You", query)

        plan = self.generate_schedule_plan(query)

        self.add_to_history("AI Assistant", plan)
        self.plan_output.configure(text=plan)

    def generate_schedule_plan(self, query):
        """
        Built-in template planner.

        Replace this method with your AI backend integration
        when that backend is available.
        """
        query_lower = query.lower()

        # Check weekly first because "weekly schedule for each day"
        # should not accidentally select the daily template.
        if "week" in query_lower:
            return (
                "📅 Weekly Planner Template\n\n"
                "Monday:    Focus on high-priority tasks\n"
                "Tuesday:   Team meetings & collaboration\n"
                "Wednesday: Deep work & project advancement\n"
                "Thursday:  Review progress & adjust plans\n"
                "Friday:    Wrap up tasks & plan ahead\n"
                "Weekend:   Rest, personal projects & learning\n\n"
                "This is a built-in template, not an AI-generated plan."
            )

        if (
            "task" in query_lower
            or "priority" in query_lower
            or "prioriti" in query_lower
        ):
            return (
                "🎯 Task Prioritization Template\n\n"
                "🔴 HIGH PRIORITY — Do First\n"
                "  • Critical project deadlines\n"
                "  • Urgent bug fixes\n"
                "  • Time-sensitive communications\n\n"
                "🟡 MEDIUM PRIORITY — Schedule Soon\n"
                "  • Feature development\n"
                "  • Code reviews\n"
                "  • Documentation updates\n\n"
                "🟢 LOW PRIORITY — When Available\n"
                "  • Refactoring\n"
                "  • Learning new tools\n"
                "  • Long-term improvements\n\n"
                "This is a built-in template, not an AI-generated plan."
            )

        if "daily" in query_lower or "day" in query_lower:
            return (
                "📋 Daily Schedule Template\n\n"
                "🌅 06:00 - 07:00  Morning routine & workout\n"
                "☕ 07:00 - 08:00  Breakfast & planning\n"
                "💻 08:00 - 10:00  Deep focus work\n"
                "🧘 10:00 - 10:15  Short break\n"
                "💻 10:15 - 12:00  Deep focus work\n"
                "🍱 12:00 - 13:00  Lunch break\n"
                "📊 13:00 - 15:00  Meetings & collaboration\n"
                "⚡ 15:00 - 17:00  Project work & tasks\n"
                "📚 17:00 - 18:00  Learning & development\n"
                "🏃 18:00 - 19:00  Exercise & wind down\n"
                "🍽 19:00 - 20:00  Dinner & family time\n"
                "🎮 20:00 - 22:00  Leisure & relaxation\n"
                "😴 22:00         Sleep preparation\n\n"
                "This is a built-in template, not an AI-generated plan."
            )

        return (
            "✨ Planning Assistant\n\n"
            f"Your request: {query}\n\n"
            "Choose Daily Schedule, Weekly Planner, or Task Priority "
            "to use a built-in planning template.\n\n"
            "Detailed personalized generation requires connecting "
            "your AI backend."
        )

    def add_to_history(self, sender, message):
        self.chat_history.append((sender, message))

        bubble = ctk.CTkFrame(
            self.history_frame,
            fg_color=(
                CARD_BG
                if sender == "You"
                else "#1E293B"
            ),
            corner_radius=8,
        )
        bubble.pack(
            fill="x",
            pady=5,
            padx=5,
        )

        ctk.CTkLabel(
            bubble,
            text=f"{sender}:",
            font=("Consolas", 11, "bold"),
            text_color=(
                ACCENT_CYAN
                if sender == "You"
                else ACCENT_PURPLE
            ),
        ).pack(
            anchor="w",
            padx=10,
            pady=(8, 2),
        )

        preview = (
            message[:150] + "..."
            if len(message) > 150
            else message
        )

        label = ctk.CTkLabel(
            bubble,
            text=preview,
            font=("Helvetica", 11),
            text_color=TEXT_LIGHT,
            wraplength=650,
            justify="left",
            anchor="w",
        )
        label.pack(
            anchor="w",
            fill="x",
            padx=10,
            pady=(0, 8),
        )

        bubble.bind(
            "<Configure>",
            lambda event, widget=label: widget.configure(
                wraplength=max(150, event.width - 25)
            ),
            add="+",
        )

    def shutdown(self):
        self._closed = True
        self._mic_stop_event.set()

        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None


# ------------------ ENTRY POINT ------------------

if __name__ == "__main__":
    app = NexusLockdownSuite(with_splash=True)
    app.mainloop()
