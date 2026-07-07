"""
gui.py
Tkinter GUI for the GitHub Profile Analyzer.
Reuses GitHubAnalyzer from analyzer.py — no changes to core logic needed.

Three distinct screens:
  1. HomeScreen    - enter username / token, big centered search
  2. LoadingScreen - animated spinner while data is fetched
  3. ResultsScreen  - tabs showing Overview / Top Repos / Charts

Run:
    python gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import math
import random
import io
import webbrowser

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from PIL import Image, ImageTk, ImageDraw

from analyzer import GitHubAnalyzer, GitHubAPIError

# ---------------------------------------------------------------------
# Pastel color palette
# ---------------------------------------------------------------------
BG = "#FDF6F0"
CARD = "#FFFFFF"
LAVENDER = "#E4D9F5"
PINK = "#FFD6E8"
MINT = "#D3F5E3"
SKY = "#D6ECFF"
PEACH = "#FFE5D4"
TEXT_DARK = "#4A3F55"
TEXT_MUTED = "#8B7E9A"
BTN_PRIMARY = "#B9A6E8"
BTN_PRIMARY_HOVER = "#A88EDE"

# Bolder / more saturated variants, used on the home screen for extra punch
BOLD_LAVENDER = "#B08CF0"
BOLD_PINK = "#FF6FAE"
BOLD_PEACH = "#FF9B54"
BOLD_SKY = "#5AB8FF"
BOLD_MINT = "#4FD8A0"
BTN_BOLD = "#8B5CF6"
BTN_BOLD_HOVER = "#7C3AED"

# --- "Nerdy" dark theme, used on the home screen ---
DARK_BG = "#0D1117"       # GitHub dark background
DARK_PANEL = "#161B22"    # slightly lighter panel
DARK_BORDER = "#30363D"
ACCENT_GREEN = "#3FB950"
ACCENT_GREEN_HOVER = "#2EA043"
ACCENT_CYAN = "#58A6FF"
TEXT_LIGHT = "#C9D1D9"
TEXT_DIM = "#8B949E"
DOT_COLOR = "#4A5560"  # brighter than the border color so the moving grid is actually visible
MONO_FONT = "Consolas"  # monospace, ships with Windows; falls back gracefully elsewhere

# --- Black & grey monochrome theme, used on the Results ("main") screen ---
BLACK = "#0A0A0A"
GREY_PANEL = "#1B1B1B"
GREY_BORDER = "#2E2E2E"
GREY_TEXT = "#9A9A9A"
WHITE_TXT = "#F2F2F2"
DOT_INACTIVE = "#3A3A3A"
DOT_ACTIVE = "#F2F2F2"

# Extra-light tints used only for the background doodle cluster
DOODLE_COLORS = ["#F3ECFB", "#FCE9F1", "#E9F8EF", "#EAF4FD", "#FDF0E6"]

RECENT_SEARCHES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recent_searches.json")
MAX_RECENT = 6


def round_rect_points(x1, y1, x2, y2, r):
    """Returns a point list that renders as a rounded rectangle when
    passed to canvas.create_polygon(..., smooth=True)."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class RoundedButton(tk.Canvas):
    """A clickable button with rounded corners, drawn on a Canvas since
    plain tk/ttk buttons can't have rounded corners. On hover it pops:
    grows slightly larger, then shrinks back to normal size on leave."""

    GROW = 5  # px of padding reserved on each side so the shape can grow without resizing the widget

    def __init__(self, parent, text, command, bg_color, hover_color,
                 fg="white", font=("Segoe UI", 12, "bold"), radius=20,
                 width=200, height=48, parent_bg=None, border_color=None, border_width=0):
        canvas_w = width + self.GROW * 2
        canvas_h = height + self.GROW * 2
        super().__init__(parent, width=canvas_w, height=canvas_h,
                          bg=parent_bg or parent["bg"], highlightthickness=0)
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg = fg
        self.font = font
        self.radius = radius
        self.base_w = width
        self.base_h = height
        self.text = text
        self.border_color = border_color
        self.border_width = border_width

        self.hovered = False
        self.inset = float(self.GROW)       # current inset from canvas edge (large = normal/small size)
        self.target_inset = float(self.GROW)
        self._animating = False

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._render()

    def _render(self):
        self.delete("all")
        x1, y1 = self.inset, self.inset
        x2, y2 = self.inset + self.base_w, self.inset + self.base_h
        color = self.hover_color if self.hovered else self.bg_color
        points = round_rect_points(x1, y1, x2, y2, self.radius)
        self.create_polygon(points, smooth=True, fill=color,
                             outline=self.border_color or "", width=self.border_width)
        self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=self.text, fill=self.fg, font=self.font)

    def set_text(self, text):
        self.text = text
        self._render()

    def _on_enter(self, event):
        self.config(cursor="hand2")
        self.hovered = True
        self._animate_to(0.0)  # inset shrinks to 0 -> shape fills the padded canvas -> looks larger

    def _on_leave(self, event):
        self.hovered = False
        self._animate_to(float(self.GROW))  # back to normal size

    def _animate_to(self, target):
        self.target_inset = target
        if not self._animating:
            self._animating = True
            self._step_animation()

    def _step_animation(self):
        diff = self.target_inset - self.inset
        if abs(diff) < 0.4:
            self.inset = self.target_inset
            self._render()
            self._animating = False
            return
        self.inset += diff * 0.45  # ease toward target for a smooth pop
        self._render()
        self.after(12, self._step_animation)

    def _on_click(self, event):
        if self.command:
            self.command()


def make_rounded_entry(parent, width_px=300, height_px=46, radius=18, show=None,
                        fill=CARD, border=LAVENDER, font=("Segoe UI", 12)):
    """Returns (canvas, entry). The canvas draws a rounded pill background;
    the plain tk.Entry is embedded inside it borderless so it blends in."""
    canvas = tk.Canvas(parent, width=width_px, height=height_px,
                        bg=parent["bg"], highlightthickness=0)
    points = round_rect_points(1, 1, width_px - 1, height_px - 1, radius)
    canvas.create_polygon(points, smooth=True, fill=fill, outline=border, width=2)
    entry = tk.Entry(canvas, font=font, bd=0, highlightthickness=0, bg=fill, fg=TEXT_DARK, show=show)
    canvas.create_window(width_px / 2, height_px / 2, window=entry, width=width_px - 34, height=height_px - 16)
    return canvas, entry

FONT_TITLE = ("Segoe UI", 26, "bold")
FONT_SUBTITLE = ("Segoe UI", 12)
FONT_HEADING = ("Segoe UI", 13, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_BODY_BOLD = ("Segoe UI", 10, "bold")


class GitHubAnalyzerApp(tk.Tk):
    """Main window. Holds a container that stacks all screens on top of
    each other; only one is raised (visible) at a time."""

    def __init__(self):
        super().__init__()
        self.title("GitHub Profile Analyzer")
        self.geometry("1920x1080")
        self.configure(bg=BG)
        self.minsize(1150, 700)

        # Shared state passed between screens
        self.username = ""
        self.token = ""
        self.top_n = 5
        self.data = None
        self.avatar_bytes = None
        self.analyzer = None
        self.recent_searches = self._load_recent_searches()
        self.current_screen = None

        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for ScreenClass in (HomeScreen, LoadingScreen, ResultsScreen):
            frame = ScreenClass(parent=container, app=self)
            self.frames[ScreenClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_screen(HomeScreen)

    def show_screen(self, screen_class):
        self.current_screen = screen_class
        frame = self.frames[screen_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    # ------------------------------------------------------------------
    # Recent searches persistence
    # ------------------------------------------------------------------
    def _load_recent_searches(self):
        try:
            with open(RECENT_SEARCHES_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[:MAX_RECENT]
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return []

    def _save_recent_search(self, username):
        self.recent_searches = [u for u in self.recent_searches if u.lower() != username.lower()]
        self.recent_searches.insert(0, username)
        self.recent_searches = self.recent_searches[:MAX_RECENT]
        try:
            with open(RECENT_SEARCHES_FILE, "w") as f:
                json.dump(self.recent_searches, f)
        except OSError:
            pass  # non-critical, just skip persistence if the file can't be written

    # ------------------------------------------------------------------
    # Analysis flow
    # ------------------------------------------------------------------
    def start_analysis(self, username, token, top_n):
        self.username = username
        self.token = token or None
        self.top_n = top_n
        self.show_screen(LoadingScreen)

        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()

    def _fetch_data(self):
        try:
            analyzer = GitHubAnalyzer(self.username, token=self.token)
            data = analyzer.summary()
            avatar_bytes = analyzer.fetch_avatar_bytes()
            self.analyzer = analyzer
            self.after(0, self._on_fetch_success, data, avatar_bytes)
        except GitHubAPIError as e:
            self.after(0, self._on_fetch_error, str(e))
        except Exception as e:
            self.after(0, self._on_fetch_error, f"Unexpected error: {e}")

    def _on_fetch_success(self, data, avatar_bytes=None):
        self.data = data
        self.avatar_bytes = avatar_bytes
        self._save_recent_search(self.username)
        self.frames[LoadingScreen].finish(lambda: self.show_screen(ResultsScreen))

    def _on_fetch_error(self, message):
        self.show_screen(HomeScreen)
        messagebox.showerror("Error", message)


# =======================================================================
# SCREEN 1: Home / Search
# =======================================================================
class HomeScreen(tk.Frame):
    """Split-screen layout, dark 'developer tool' aesthetic: a terminal-style
    brand panel on the left, a matching dark form panel on the right."""

    LEFT_FRAC = 42
    RIGHT_FRAC = 58

    def __init__(self, parent, app):
        super().__init__(parent, bg=DARK_PANEL)
        self.app = app
        self.dot_offset = 0
        self._dots_animating = False

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=self.LEFT_FRAC)
        self.grid_columnconfigure(1, weight=self.RIGHT_FRAC)

        # ---------------- LEFT: terminal / mark panel ----------------
        self.left_canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=DARK_BG)
        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_canvas.bind("<Configure>", self._draw_left_panel)

        # ---------------- RIGHT: form panel ----------------
        right = tk.Frame(self, bg=DARK_PANEL)
        right.grid(row=0, column=1, sticky="nsew")

        form_wrap = tk.Frame(right, bg=DARK_PANEL)
        form_wrap.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form_wrap, text="GIT ANALYZER", font=(MONO_FONT, 24, "bold"),
                 bg=DARK_PANEL, fg=ACCENT_GREEN).pack(anchor="w")
        tk.Label(form_wrap, text="// Pull public stats for any GitHub profile",
                 font=(MONO_FONT, 10), bg=DARK_PANEL, fg=TEXT_DIM).pack(anchor="w", pady=(2, 28))

        tk.Label(form_wrap, text="USERNAME", font=(MONO_FONT, 9, "bold"),
                 bg=DARK_PANEL, fg=TEXT_DIM).pack(anchor="w", pady=(0, 4))
        username_canvas, self.username_entry = make_rounded_entry(
            form_wrap, width_px=340, height_px=46, radius=23, fill=DARK_BG,
            border=DARK_BORDER, font=(MONO_FONT, 12)
        )
        self.username_entry.config(fg=TEXT_LIGHT, insertbackground=ACCENT_GREEN)
        username_canvas.pack(anchor="w", pady=(0, 22))
        self.username_entry.insert(0, "octocat")
        self.username_entry.bind("<Return>", lambda e: self.on_analyze())

        tk.Label(form_wrap, text="TOP REPOS TO SHOW", font=(MONO_FONT, 9, "bold"),
                 bg=DARK_PANEL, fg=TEXT_DIM).pack(anchor="w", pady=(0, 4))
        self.top_n = 5
        topn_row = tk.Frame(form_wrap, bg=DARK_PANEL)
        topn_row.pack(anchor="w", pady=(0, 26))

        self.topn_minus_btn = RoundedButton(
            topn_row, text="–", command=lambda: self._adjust_top_n(-1),
            bg_color=DARK_BG, hover_color=DARK_BORDER, fg=ACCENT_CYAN,
            font=(MONO_FONT, 14, "bold"), radius=23, width=46, height=46,
            parent_bg=DARK_PANEL, border_color=DARK_BORDER, border_width=1
        )
        self.topn_minus_btn.pack(side="left")

        self.topn_display = tk.Canvas(topn_row, width=64, height=46, bg=DARK_PANEL, highlightthickness=0)
        self.topn_display.pack(side="left", padx=10)
        self._draw_topn_display()

        self.topn_plus_btn = RoundedButton(
            topn_row, text="+", command=lambda: self._adjust_top_n(1),
            bg_color=DARK_BG, hover_color=DARK_BORDER, fg=ACCENT_CYAN,
            font=(MONO_FONT, 14, "bold"), radius=23, width=46, height=46,
            parent_bg=DARK_PANEL, border_color=DARK_BORDER, border_width=1
        )
        self.topn_plus_btn.pack(side="left")

        self.analyze_btn = RoundedButton(
            form_wrap, text="▶  Run Analysis", command=self.on_analyze,
            bg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER, fg=DARK_BG,
            font=(MONO_FONT, 13, "bold"), radius=27, width=340, height=54, parent_bg=DARK_PANEL
        )
        self.analyze_btn.pack(anchor="w")

        tk.Label(form_wrap, text="# Tip: works with any public GitHub profile, no login needed",
                 font=(MONO_FONT, 8), bg=DARK_PANEL, fg=TEXT_DIM, wraplength=340, justify="left").pack(
            anchor="w", pady=(10, 0)
        )

        self.recent_label = tk.Label(form_wrap, text="RECENT", font=(MONO_FONT, 9, "bold"),
                                      bg=DARK_PANEL, fg=TEXT_DIM)
        self.recent_frame = tk.Frame(form_wrap, bg=DARK_PANEL)

        self.form_wrap = form_wrap

    # ------------------------------------------------------------------
    def _draw_topn_display(self):
        c = self.topn_display
        c.delete("all")
        points = round_rect_points(1, 1, 63, 45, 23)
        c.create_polygon(points, smooth=True, fill=DARK_BG, outline=DARK_BORDER, width=1)
        c.create_text(32, 23, text=str(self.top_n), font=(MONO_FONT, 15, "bold"), fill=TEXT_LIGHT)

    def _adjust_top_n(self, delta):
        self.top_n = max(1, min(20, self.top_n + delta))
        self._draw_topn_display()

    # ------------------------------------------------------------------
    # Left panel: dark terminal background + original cat/octopus mark
    # ------------------------------------------------------------------
    def _draw_left_panel(self, event=None):
        c = self.left_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return

        c.create_rectangle(0, 0, w, h, fill=DARK_BG, outline="", tags="bg_rect")

        # --- Original cat + tentacle mark (not a copy of any existing logo) ---
        cx, cy = w * 0.5, h * 0.18
        badge_r = 44
        c.create_oval(cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r,
                       fill=ACCENT_GREEN, outline="")
        # cat ears
        c.create_polygon(cx - 26, cy - 18, cx - 8, cy - 40, cx - 4, cy - 14,
                          fill=DARK_BG, outline="")
        c.create_polygon(cx + 26, cy - 18, cx + 8, cy - 40, cx + 4, cy - 14,
                          fill=DARK_BG, outline="")
        # face
        c.create_oval(cx - 22, cy - 20, cx + 22, cy + 16, fill=DARK_BG, outline="")
        # eyes
        c.create_oval(cx - 10, cy - 6, cx - 5, cy - 1, fill=ACCENT_GREEN, outline="")
        c.create_oval(cx + 5, cy - 6, cx + 10, cy - 1, fill=ACCENT_GREEN, outline="")
        # tentacle legs beneath the face
        for i, dx in enumerate([-18, -8, 0, 8, 18]):
            start_x = cx + dx
            start_y = cy + 14
            wobble = 6 if i % 2 == 0 else -6
            c.create_line(
                start_x, start_y, start_x + wobble, start_y + 14, start_x, start_y + 26,
                fill=DARK_BG, width=5, smooth=True, capstyle="round"
            )

        c.create_text(w * 0.5, h * 0.32, text="GitHub Profile Analyzer",
                       font=(MONO_FONT, 18, "bold"), fill=TEXT_LIGHT, justify="center")
        c.create_text(w * 0.5, h * 0.375, text="> Deep-dive into any public profile_",
                       font=(MONO_FONT, 10), fill=ACCENT_GREEN, justify="center")

        # Terminal-style feature list, like commented-out code
        features = [
            "// Ranked top repositories",
            "// Language breakdown",
            "// Visual charts",
            "// No login required",
        ]
        start_y = h * 0.52
        for i, feat in enumerate(features):
            c.create_text(w * 0.5, start_y + i * 30, text=feat, font=(MONO_FONT, 11),
                           fill=TEXT_DIM, anchor="center")

        # Small git-graph doodle near the bottom
        self._draw_git_graph(c, w * 0.5, h * 0.78)

        # Animated dot-grid texture, drawn last then sent behind everything else
        self._draw_dots()
        c.tag_raise("dots", "bg_rect")

    def _draw_dots(self):
        """Draws the drifting dot-grid texture. Called on a timer to animate,
        and after every full redraw (resize) to keep it in sync."""
        c = self.left_canvas
        c.delete("dots")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return
        step = 34
        offset = self.dot_offset % step
        for gx in range(-step, int(w) + step, step):
            for gy in range(-step, int(h) + step, step):
                x, y = gx + offset, gy + offset
                c.create_oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5, fill=DOT_COLOR, outline="", tags="dots")

    def _animate_dots(self):
        if self.app.current_screen is not HomeScreen:
            self._dots_animating = False
            return
        self.dot_offset = (self.dot_offset + 1.2) % 34
        self._draw_dots()
        self.left_canvas.tag_raise("dots", "bg_rect")
        self.after(40, self._animate_dots)

    def _draw_git_graph(self, c, cx, cy):
        color = ACCENT_CYAN
        c.create_line(cx - 60, cy, cx - 60, cy + 50, fill=color, width=3)
        c.create_line(cx - 60, cy + 15, cx, cy + 15, fill=color, width=3)
        c.create_line(cx, cy + 15, cx, cy + 50, fill=color, width=3)
        c.create_line(cx + 60, cy, cx + 60, cy + 30, fill=color, width=3)
        c.create_line(cx + 60, cy + 30, cx, cy + 45, fill=color, width=3)
        for px, py in [(cx - 60, cy), (cx - 60, cy + 50), (cx, cy + 15),
                       (cx, cy + 50), (cx + 60, cy), (cx + 60, cy + 30)]:
            c.create_oval(px - 5, py - 5, px + 5, py + 5, fill=DARK_BG, outline=color, width=2)

    # ------------------------------------------------------------------
    def on_show(self):
        self.username_entry.focus_set()
        self._refresh_recent_chips()
        self.after(50, self._draw_left_panel)
        if not self._dots_animating:
            self._dots_animating = True
            self.after(40, self._animate_dots)

    def _refresh_recent_chips(self):
        for widget in self.recent_frame.winfo_children():
            widget.destroy()

        if not self.app.recent_searches:
            self.recent_label.pack_forget()
            self.recent_frame.pack_forget()
            return

        self.recent_label.pack(anchor="w", pady=(20, 6))
        self.recent_frame.pack(anchor="w")

        for username in self.app.recent_searches:
            chip_width = max(64, 11 * len(username) + 28)
            chip = RoundedButton(
                self.recent_frame, text=username, command=lambda u=username: self._use_recent(u),
                bg_color=DARK_BG, hover_color=DARK_BORDER, fg=ACCENT_GREEN,
                font=(MONO_FONT, 9), radius=15, width=chip_width, height=30,
                parent_bg=DARK_PANEL, border_color=DARK_BORDER, border_width=1
            )
            chip.pack(side="left", padx=(0, 6), pady=2)

    def _use_recent(self, username):
        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, username)
        self.on_analyze()

    def on_analyze(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showwarning("Missing username", "Please enter a GitHub username.")
            return
        self.app.start_analysis(username, None, self.top_n)


GITHUB_FACTS = [
    "GitHub was founded in 2008 by Tom Preston-Werner, Chris Wanstrath, and PJ Hyett.",
    "Git was created by Linus Torvalds in 2005 to help maintain the Linux kernel.",
    "The name 'Git' is British slang for an unpleasant person — Linus said he names things after himself.",
    "Microsoft acquired GitHub in 2018 for about $7.5 billion.",
    "GitHub's mascot, the Octocat, was designed by Simon Oxley and first appeared in 2008.",
    "As of the mid-2020s, GitHub hosts well over 100 million developers worldwide.",
    "The largest GitHub repositories can contain millions of commits spanning many years.",
    "GitHub Pages lets you host a static website directly from a repository, for free.",
    "The green squares on a GitHub profile are called the 'contribution graph.'",
    "GitHub Actions, launched in 2019, lets you automate workflows directly in your repo.",
    "Git uses SHA-1 hashes to uniquely identify every commit in a repository's history.",
    "A 'fork' lets you create your own copy of someone else's repository to modify freely.",
    "GitHub Copilot, an AI pair programmer, was first previewed in 2021.",
    "The '.git' folder in a repository contains the entire history of the project.",
    "GitHub's first commit was made by Tom Preston-Werner back in 2007.",
    "You can navigate many GitHub pages entirely with keyboard shortcuts, like pressing 't' to search files.",
    "Linus Torvalds reportedly built the first version of Git in about 10 days.",
    "GitHub Sponsors lets developers get paid directly for their open-source work.",
    "Some of the most-starred repositories on GitHub are free-code-camp and awesome lists of curated resources.",
    "A 'pull request' is how changes from one branch or fork are proposed to be merged into another.",
]


# =======================================================================
# SCREEN 2: Loading
# =======================================================================
class LoadingScreen(tk.Frame):
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    MESSAGES = [
        "> connecting to api.github.com",
        "> fetching profile data",
        "> fetching repositories",
        "> computing language breakdown",
        "> ranking top repositories",
    ]
    SEGMENTS = 24  # number of chunky blocks in the retro progress bar
    PROGRESS_CAP = 92  # simulated progress creeps up to here, then finish() jumps it to 100
    FACTS = GITHUB_FACTS

    def __init__(self, parent, app):
        super().__init__(parent, bg=DARK_BG)
        self.app = app

        self.dot_offset = 0
        self._dots_animating = False
        self.spinner_index = 0
        self._spinner_animating = False
        self.message_index = 0
        self._messages_animating = False
        self.fact_index = 0
        self._facts_animating = False
        self.percent = 0.0
        self._progress_animating = False
        self._finishing = False

        self.canvas = tk.Canvas(self, bg=DARK_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._draw_static)

    # ------------------------------------------------------------------
    def on_show(self):
        self.spinner_index = 0
        self.message_index = 0
        self.fact_index = random.randrange(len(self.FACTS))
        self.percent = 0.0
        self._finishing = False
        self.after(30, self._draw_static)

        if not self._dots_animating:
            self._dots_animating = True
            self.after(40, self._animate_dots)
        if not self._spinner_animating:
            self._spinner_animating = True
            self.after(90, self._animate_spinner)
        if not self._messages_animating:
            self._messages_animating = True
            self.after(900, self._animate_messages)
        if not self._facts_animating:
            self._facts_animating = True
            self.after(4000, self._animate_facts)
        if not self._progress_animating:
            self._progress_animating = True
            self.after(80, self._animate_progress)

    def finish(self, callback):
        """Called by the app once real data has arrived: quickly finishes
        the bar to 100% instead of leaving it stuck mid-way, then continues."""
        self._finishing = True
        self._finish_callback = callback
        self._step_finish()

    def _step_finish(self):
        if self.percent < 100:
            self.percent = min(100, self.percent + 6)
            self._draw_bar_fill()
            self._draw_percent_text()
            self.after(12, self._step_finish)
        else:
            self.after(250, self._finish_callback)

    # ------------------------------------------------------------------
    # Static layout: background, cat mark, title, bar frame. Redrawn on resize.
    # ------------------------------------------------------------------
    def _draw_static(self, event=None):
        c = self.canvas
        c.delete("static")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return
        self.w, self.h = w, h

        c.create_rectangle(0, 0, w, h, fill=DARK_BG, outline="", tags=("static", "bg_rect"))

        cx, cy = w * 0.5, h * 0.30
        badge_r = 40
        c.create_oval(cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r,
                       fill=ACCENT_GREEN, outline="", tags="static")
        c.create_polygon(cx - 24, cy - 16, cx - 7, cy - 36, cx - 3, cy - 12,
                          fill=DARK_BG, outline="", tags="static")
        c.create_polygon(cx + 24, cy - 16, cx + 7, cy - 36, cx + 3, cy - 12,
                          fill=DARK_BG, outline="", tags="static")
        c.create_oval(cx - 20, cy - 18, cx + 20, cy + 14, fill=DARK_BG, outline="", tags="static")
        c.create_oval(cx - 9, cy - 5, cx - 4, cy, fill=ACCENT_GREEN, outline="", tags="static")
        c.create_oval(cx + 4, cy - 5, cx + 9, cy, fill=ACCENT_GREEN, outline="", tags="static")
        for i, dx in enumerate([-16, -7, 0, 7, 16]):
            sx, sy = cx + dx, cy + 12
            wob = 5 if i % 2 == 0 else -5
            c.create_line(sx, sy, sx + wob, sy + 12, sx, sy + 22,
                           fill=DARK_BG, width=4, smooth=True, capstyle="round", tags="static")

        c.create_text(w * 0.5, h * 0.44, text=f"Analyzing '{self.app.username}'",
                       font=(MONO_FONT, 18, "bold"), fill=TEXT_LIGHT, tags="static")

        # Retro chunky progress bar frame (sharp corners, Windows-95-style)
        bar_w, bar_h = 380, 24
        bx1 = w * 0.5 - bar_w / 2
        by1 = h * 0.56
        bx2, by2 = bx1 + bar_w, by1 + bar_h
        self.bar_bounds = (bx1, by1, bx2, by2)
        c.create_rectangle(bx1 - 3, by1 - 3, bx2 + 3, by2 + 3, outline=DARK_BORDER, width=2, tags="static")
        c.create_rectangle(bx1, by1, bx2, by2, fill=DARK_PANEL, outline="", tags="static")

        self._draw_dots()
        c.tag_raise("dots", "bg_rect")
        self._draw_spinner_line()
        self._draw_bar_fill()
        self._draw_percent_text()
        self._draw_fact_text()

    # ------------------------------------------------------------------
    # Animated pieces, each redraws only its own tag
    # ------------------------------------------------------------------
    def _draw_spinner_line(self):
        c = self.canvas
        c.delete("spinner")
        if not hasattr(self, "w"):
            return
        frame = self.SPINNER_FRAMES[self.spinner_index]
        message = self.MESSAGES[self.message_index]
        c.create_text(self.w * 0.5, self.h * 0.50, text=f"{frame}  {message}",
                       font=(MONO_FONT, 11), fill=ACCENT_GREEN, tags="spinner")

    def _draw_bar_fill(self):
        """Draws the bar as a row of discrete square blocks, like the
        classic Windows 95/98 installer progress bar, instead of a
        smooth continuous fill."""
        c = self.canvas
        c.delete("bar_fill")
        if not hasattr(self, "bar_bounds"):
            return
        bx1, by1, bx2, by2 = self.bar_bounds
        gap = 3
        total_w = bx2 - bx1
        seg_w = (total_w - gap * (self.SEGMENTS - 1)) / self.SEGMENTS
        filled = int(round(self.percent / 100 * self.SEGMENTS))

        x = bx1
        for i in range(self.SEGMENTS):
            if i < filled:
                c.create_rectangle(x, by1 + 3, x + seg_w, by2 - 3,
                                    fill=ACCENT_GREEN, outline="", tags="bar_fill")
            x += seg_w + gap

    def _draw_percent_text(self):
        c = self.canvas
        c.delete("percent_text")
        if not hasattr(self, "w"):
            return
        c.create_text(self.w * 0.5, self.h * 0.56 + 24 + 26, text=f"{int(self.percent)}%",
                       font=(MONO_FONT, 14, "bold"), fill=ACCENT_GREEN, tags="percent_text")

    def _draw_fact_text(self):
        c = self.canvas
        c.delete("fact_text")
        if not hasattr(self, "w"):
            return
        fact = self.FACTS[self.fact_index]
        c.create_text(self.w * 0.5, self.h * 0.74, text="💡 Did you know?",
                       font=(MONO_FONT, 10, "bold"), fill=TEXT_DIM, tags="fact_text")
        c.create_text(self.w * 0.5, self.h * 0.79, text=fact,
                       font=(MONO_FONT, 11), fill=TEXT_LIGHT, width=int(self.w * 0.55),
                       justify="center", tags="fact_text")

    def _draw_dots(self):
        c = self.canvas
        c.delete("dots")
        if not hasattr(self, "w"):
            return
        step = 34
        offset = self.dot_offset % step
        for gx in range(-step, int(self.w) + step, step):
            for gy in range(-step, int(self.h) + step, step):
                x, y = gx + offset, gy + offset
                c.create_oval(x - 1.5, y - 1.5, x + 1.5, y + 1.5, fill=DOT_COLOR, outline="", tags="dots")

    # ------------------------------------------------------------------
    # Timers - each self-terminates once we've left this screen
    # ------------------------------------------------------------------
    def _animate_dots(self):
        if self.app.current_screen is not LoadingScreen:
            self._dots_animating = False
            return
        self.dot_offset = (self.dot_offset + 1.2) % 34
        self._draw_dots()
        self.canvas.tag_raise("dots", "bg_rect")
        self.after(40, self._animate_dots)

    def _animate_spinner(self):
        if self.app.current_screen is not LoadingScreen:
            self._spinner_animating = False
            return
        self.spinner_index = (self.spinner_index + 1) % len(self.SPINNER_FRAMES)
        self._draw_spinner_line()
        self.after(90, self._animate_spinner)

    def _animate_messages(self):
        if self.app.current_screen is not LoadingScreen:
            self._messages_animating = False
            return
        self.message_index = (self.message_index + 1) % len(self.MESSAGES)
        self._draw_spinner_line()
        self.after(900, self._animate_messages)

    def _animate_facts(self):
        if self.app.current_screen is not LoadingScreen:
            self._facts_animating = False
            return
        self.fact_index = (self.fact_index + 1) % len(self.FACTS)
        self._draw_fact_text()
        self.after(4000, self._animate_facts)

    def _animate_progress(self):
        if self.app.current_screen is not LoadingScreen:
            self._progress_animating = False
            return
        if not self._finishing and self.percent < self.PROGRESS_CAP:
            remaining = self.PROGRESS_CAP - self.percent
            # Slow, gentle crawl — small enough that ~15-20s pass before hitting
            # the cap, giving the rotating facts time to actually be read.
            self.percent += remaining * 0.006 + 0.05
            self.percent = min(self.percent, self.PROGRESS_CAP)
            self._draw_bar_fill()
            self._draw_percent_text()
        self.after(80, self._animate_progress)


# =======================================================================
# SCREEN 3: Results
# =======================================================================
class ResultsScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BLACK)
        self.app = app
        self.avatar_photo = None  # keep a reference so Tkinter doesn't garbage-collect it
        self.current_view = "overview"

        # --- Header bar ---
        header = tk.Frame(self, bg=GREY_PANEL, height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        self.header_label = tk.Label(header, text="", font=(MONO_FONT, 15, "bold"),
                                      bg=GREY_PANEL, fg=WHITE_TXT)
        self.header_label.pack(side="left", padx=24, pady=10)

        right_controls = tk.Frame(header, bg=GREY_PANEL)
        right_controls.pack(side="right", padx=24, pady=10)

        back_btn = RoundedButton(
            right_controls, text="← New Search", command=self.on_back,
            bg_color=BLACK, hover_color=GREY_BORDER, fg=WHITE_TXT,
            font=(MONO_FONT, 10, "bold"), radius=12, width=150, height=38,
            parent_bg=GREY_PANEL, border_color=GREY_BORDER, border_width=1
        )
        back_btn.pack(side="right")

        self.menu_btn = RoundedButton(
            right_controls, text="⋮", command=self._open_menu,
            bg_color=BLACK, hover_color=GREY_BORDER, fg=WHITE_TXT,
            font=(MONO_FONT, 14, "bold"), radius=12, width=46, height=38,
            parent_bg=GREY_PANEL, border_color=GREY_BORDER, border_width=1
        )
        self.menu_btn.pack(side="right", padx=(0, 10))

        # --- ttk styling shared by the repos Treeview ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Mono.Treeview", background=GREY_PANEL, fieldbackground=GREY_PANEL,
                         foreground=WHITE_TXT, font=(MONO_FONT, 10), borderwidth=0, rowheight=28)
        style.configure("Mono.Treeview.Heading", background=GREY_BORDER, foreground=WHITE_TXT,
                         font=(MONO_FONT, 10, "bold"), borderwidth=0)
        style.map("Mono.Treeview", background=[("selected", WHITE_TXT)], foreground=[("selected", BLACK)])

        # --- Content container: three views stacked, only one raised at a time ---
        content = tk.Frame(self, bg=BLACK)
        content.pack(fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.overview_frame = tk.Frame(content, bg=BLACK)
        self.repos_frame = tk.Frame(content, bg=BLACK)
        self.charts_frame = tk.Frame(content, bg=BLACK)
        self.repo_detail_frame = tk.Frame(content, bg=BLACK)

        for frame in (self.overview_frame, self.repos_frame, self.charts_frame, self.repo_detail_frame):
            frame.grid(row=0, column=0, sticky="nsew")

    def on_back(self):
        self.app.show_screen(HomeScreen)

    def on_show(self):
        data = self.app.data
        if not data:
            return
        self.header_label.config(text=f"{data['name'] or data['username']}  (@{data['username']})")
        self._load_avatar()
        self._render_overview(data)
        self._render_repos(data)
        self._render_charts(data)
        self._show_view("overview")

    # ------------------------------------------------------------------
    # Three-dot menu: the only way to reach Top Repos / Charts / back to Overview
    # ------------------------------------------------------------------
    def _open_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=GREY_PANEL, fg=WHITE_TXT,
                        activebackground=GREY_BORDER, activeforeground=WHITE_TXT,
                        font=(MONO_FONT, 12, "bold"), borderwidth=0,
                        relief="flat")
        menu.add_command(label="  Overview", command=lambda: self._show_view("overview"))
        menu.add_command(label="  Top Repos", command=lambda: self._show_view("repos"))
        menu.add_command(label="  Charts", command=lambda: self._show_view("charts"))
        x = self.menu_btn.winfo_rootx()
        y = self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height() + 4
        menu.tk_popup(x, y)

    def _show_view(self, name):
        self.current_view = name
        frame = {
            "overview": self.overview_frame, "repos": self.repos_frame,
            "charts": self.charts_frame, "repo_detail": self.repo_detail_frame,
        }[name]
        frame.tkraise()

    # ------------------------------------------------------------------
    # Avatar: download already happened in the background thread; here
    # we just decode it and crop it into a circle for the Instagram look.
    # ------------------------------------------------------------------
    def _load_avatar(self, size=110):
        avatar_bytes = self.app.avatar_bytes
        if not avatar_bytes:
            self.avatar_photo = None
            return
        try:
            img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            self.avatar_photo = ImageTk.PhotoImage(img)
        except Exception:
            self.avatar_photo = None

    # ------------------------------------------------------------------
    def _clear(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    # ------------------------------------------------------------------
    # Overview: a single page with everything about the person, no
    # pagination — avatar/IG-style stats up top, then extended stats,
    # then a featured top-repo card, all stacked in one scroll-free view.
    # ------------------------------------------------------------------
    def _render_overview(self, data):
        self._clear(self.overview_frame)

        canvas = tk.Canvas(self.overview_frame, bg=BLACK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.overview_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        frame = tk.Frame(canvas, bg=BLACK)
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event):
            canvas.itemconfig(frame_id, width=event.width)

        frame.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)

        pad = tk.Frame(frame, bg=BLACK)
        pad.pack(fill="both", expand=True, padx=50, pady=36)

        # --- Profile header row: avatar + IG-style stat row ---
        top_row = tk.Frame(pad, bg=BLACK)
        top_row.pack(fill="x")

        profile_url = f"https://github.com/{data['username']}"

        def _open_profile(event=None):
            webbrowser.open(profile_url)

        def _bind_link(widget, hover_widget=None, hover_fg=None, base_fg=None):
            widget.config(cursor="hand2")
            widget.bind("<Button-1>", _open_profile)
            if hover_widget is not None:
                widget.bind("<Enter>", lambda e: hover_widget.config(fg=hover_fg))
                widget.bind("<Leave>", lambda e: hover_widget.config(fg=base_fg))

        if self.avatar_photo:
            avatar_label = tk.Label(top_row, image=self.avatar_photo, bg=BLACK)
            avatar_label.pack(side="left", padx=(0, 36))
            _bind_link(avatar_label)
        else:
            placeholder = tk.Canvas(top_row, width=110, height=110, bg=BLACK, highlightthickness=0)
            placeholder.create_oval(2, 2, 108, 108, fill=GREY_PANEL, outline=GREY_BORDER, width=2)
            placeholder.create_text(55, 55, text="👤", font=(MONO_FONT, 32))
            placeholder.pack(side="left", padx=(0, 36))
            placeholder.config(cursor="hand2")
            placeholder.bind("<Button-1>", _open_profile)

        stats_row = tk.Frame(top_row, bg=BLACK)
        stats_row.pack(side="left", fill="x", expand=True)

        ig_stats = [
            ("Repos", data["public_repos"]),
            ("Followers", data["followers"]),
            ("Following", data["following"]),
        ]
        for label, value in ig_stats:
            cell = tk.Frame(stats_row, bg=BLACK)
            cell.pack(side="left", expand=True)
            tk.Label(cell, text=str(value), font=(MONO_FONT, 20, "bold"), bg=BLACK, fg=WHITE_TXT).pack()
            tk.Label(cell, text=label, font=(MONO_FONT, 10), bg=BLACK, fg=GREY_TEXT).pack()

        name_label = tk.Label(pad, text=data["name"] or data["username"], font=(MONO_FONT, 16, "bold"),
                               bg=BLACK, fg=WHITE_TXT)
        name_label.pack(anchor="w", pady=(26, 0))
        _bind_link(name_label, hover_widget=name_label, hover_fg=ACCENT_CYAN, base_fg=WHITE_TXT)

        username_label = tk.Label(pad, text=f"@{data['username']}  ↗", font=(MONO_FONT, 10), bg=BLACK, fg=ACCENT_CYAN)
        username_label.pack(anchor="w")
        _bind_link(username_label)
        tk.Label(pad, text="Click the avatar, name, or username above to view this profile on GitHub",
                 font=(MONO_FONT, 9), bg=BLACK, fg=GREY_TEXT).pack(anchor="w", pady=(4, 0))

        if data["bio"]:
            tk.Label(pad, text=data["bio"], font=(MONO_FONT, 11), bg=BLACK, fg=WHITE_TXT,
                     wraplength=750, justify="left").pack(anchor="w", pady=(14, 0))
        if data["location"]:
            tk.Label(pad, text=f"📍 {data['location']}", font=(MONO_FONT, 10), bg=BLACK, fg=GREY_TEXT).pack(
                anchor="w", pady=(10, 0)
            )

        # --- Extended stats row ---
        tk.Label(pad, text="Stats", font=(MONO_FONT, 13, "bold"), bg=BLACK, fg=WHITE_TXT).pack(
            anchor="w", pady=(34, 14)
        )
        grid = tk.Frame(pad, bg=BLACK)
        grid.pack(fill="x")
        cards = [
            ("⭐ Total stars", data["total_stars"]),
            ("🍴 Total forks", data["total_forks"]),
            ("📅 Account age", f"{data['account_age_years']} yrs"),
        ]
        for i, (label, value) in enumerate(cards):
            card = tk.Frame(grid, bg=GREY_PANEL, padx=24, pady=20,
                             highlightbackground=GREY_BORDER, highlightthickness=1)
            card.grid(row=0, column=i, padx=10, sticky="nsew")
            tk.Label(card, text=str(value), font=(MONO_FONT, 18, "bold"), bg=GREY_PANEL, fg=WHITE_TXT).pack()
            tk.Label(card, text=label, font=(MONO_FONT, 10), bg=GREY_PANEL, fg=GREY_TEXT).pack(pady=(6, 0))
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)

        # --- Featured top-repo card ---
        tk.Label(pad, text="Top Repository", font=(MONO_FONT, 13, "bold"), bg=BLACK, fg=WHITE_TXT).pack(
            anchor="w", pady=(34, 14)
        )
        top_repos = data.get("top_repos") or []
        if top_repos:
            repo = top_repos[0]
            card = tk.Frame(pad, bg=GREY_PANEL, padx=28, pady=24,
                             highlightbackground=GREY_BORDER, highlightthickness=1)
            card.pack(fill="x")
            tk.Label(card, text=repo["name"], font=(MONO_FONT, 15, "bold"), bg=GREY_PANEL, fg=WHITE_TXT).pack(
                anchor="w"
            )
            if repo.get("description"):
                tk.Label(card, text=repo["description"], font=(MONO_FONT, 10), bg=GREY_PANEL, fg=GREY_TEXT,
                         wraplength=650, justify="left").pack(anchor="w", pady=(8, 0))
            stat_row = tk.Frame(card, bg=GREY_PANEL)
            stat_row.pack(anchor="w", pady=(14, 0))
            tk.Label(stat_row, text=f"⭐ {repo.get('stargazers_count', 0)}", font=(MONO_FONT, 11, "bold"),
                     bg=GREY_PANEL, fg=WHITE_TXT).pack(side="left", padx=(0, 22))
            tk.Label(stat_row, text=f"🍴 {repo.get('forks_count', 0)}", font=(MONO_FONT, 11, "bold"),
                     bg=GREY_PANEL, fg=WHITE_TXT).pack(side="left")
        else:
            tk.Label(pad, text="No public repositories found.", font=(MONO_FONT, 11),
                     bg=BLACK, fg=GREY_TEXT).pack(anchor="w")

    # ------------------------------------------------------------------
    def _render_repos(self, data):
        self._clear(self.repos_frame)

        # Scrollable canvas so any number of repo cards can stack vertically
        outer = tk.Frame(self.repos_frame, bg=BLACK)
        outer.pack(fill="both", expand=True, padx=30, pady=24)

        tk.Label(outer, text="TOP REPOSITORIES", font=(MONO_FONT, 20, "bold"),
                 bg=BLACK, fg=WHITE_TXT).pack(anchor="w", pady=(0, 2))
        tk.Label(outer, text="Ranked by stars  ·  click a card for full details", font=(MONO_FONT, 10),
                 bg=BLACK, fg=GREY_TEXT).pack(anchor="w", pady=(0, 18))

        canvas = tk.Canvas(outer, bg=BLACK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        list_frame = tk.Frame(canvas, bg=BLACK)

        list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        repos = data["top_repos"][: self.app.top_n]
        RANK_COLORS = ["#FFD54A", "#D9D9D9", "#C77B3C"]  # gold / silver / bronze for top 3

        for i, repo in enumerate(repos):
            rank_color = RANK_COLORS[i] if i < 3 else GREY_TEXT
            card = tk.Frame(list_frame, bg=GREY_PANEL, highlightbackground=GREY_BORDER,
                             highlightthickness=1)
            card.pack(fill="x", pady=7)

            inner = tk.Frame(card, bg=GREY_PANEL)
            inner.pack(fill="both", expand=True, padx=20, pady=16)

            top_row = tk.Frame(inner, bg=GREY_PANEL)
            top_row.pack(fill="x")

            tk.Label(top_row, text=f"#{i + 1}", font=(MONO_FONT, 18, "bold"),
                     bg=GREY_PANEL, fg=rank_color).pack(side="left", padx=(0, 14))

            name_col = tk.Frame(top_row, bg=GREY_PANEL)
            name_col.pack(side="left", fill="x", expand=True)
            tk.Label(name_col, text=repo["name"], font=(MONO_FONT, 17, "bold"),
                     bg=GREY_PANEL, fg=WHITE_TXT, anchor="w").pack(fill="x")

            desc = (repo.get("description") or "No description provided.")
            if len(desc) > 110:
                desc = desc[:107] + "..."
            tk.Label(inner, text=desc, font=(MONO_FONT, 10), bg=GREY_PANEL, fg=GREY_TEXT,
                     anchor="w", justify="left", wraplength=760).pack(fill="x", pady=(8, 12))

            stat_row = tk.Frame(inner, bg=GREY_PANEL)
            stat_row.pack(fill="x")
            tk.Label(stat_row, text=f"⭐ {repo.get('stargazers_count', 0):,}",
                     font=(MONO_FONT, 12, "bold"), bg=GREY_PANEL, fg=WHITE_TXT).pack(side="left", padx=(0, 24))
            tk.Label(stat_row, text=f"🍴 {repo.get('forks_count', 0):,}",
                     font=(MONO_FONT, 12, "bold"), bg=GREY_PANEL, fg=WHITE_TXT).pack(side="left", padx=(0, 24))
            lang = repo.get("language")
            if lang:
                tk.Label(stat_row, text=lang, font=(MONO_FONT, 10, "bold"),
                         bg=GREY_BORDER, fg=WHITE_TXT, padx=10, pady=3).pack(side="right")

            # Whole card is clickable, with a subtle hover highlight
            clickable_widgets = [card, inner, top_row, name_col, stat_row] + \
                list(inner.winfo_children()) + list(top_row.winfo_children()) + \
                list(name_col.winfo_children()) + list(stat_row.winfo_children())

            def on_enter(e, c=card):
                c.configure(bg=GREY_BORDER, highlightbackground=WHITE_TXT)
                for w in c.winfo_children():
                    self._set_bg_recursive(w, GREY_BORDER)

            def on_leave(e, c=card):
                c.configure(bg=GREY_PANEL, highlightbackground=GREY_BORDER)
                for w in c.winfo_children():
                    self._set_bg_recursive(w, GREY_PANEL)

            for w in clickable_widgets:
                w.bind("<Button-1>", lambda e, r=repo: self._show_repo_detail(r))
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.configure(cursor="hand2")

    def _set_bg_recursive(self, widget, color):
        try:
            # Don't recolor the language-tag chip; it keeps its own accent bg
            if widget.cget("bg") != GREY_BORDER or widget.master.cget("bg") == GREY_PANEL:
                widget.configure(bg=color)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_bg_recursive(child, color)

    # ------------------------------------------------------------------
    # Repo detail view: full stats + per-repo language chart, opened by
    # clicking a row in Top Repos. Clicking the repo name opens it on GitHub.
    # ------------------------------------------------------------------
    def _show_repo_detail(self, repo):
        self._render_repo_detail(repo)
        self._show_view("repo_detail")

    def _render_repo_detail(self, repo):
        self._clear(self.repo_detail_frame)
        wrap = tk.Frame(self.repo_detail_frame, bg=BLACK)
        wrap.pack(fill="both", expand=True, padx=40, pady=30)

        RoundedButton(
            wrap, text="← Back to Top Repos", command=lambda: self._show_view("repos"),
            bg_color=BLACK, hover_color=GREY_BORDER, fg=WHITE_TXT,
            font=(MONO_FONT, 10, "bold"), radius=12, width=190, height=38,
            parent_bg=BLACK, border_color=GREY_BORDER, border_width=1
        ).pack(anchor="w", pady=(0, 20))

        html_url = repo.get("html_url", "")
        name_btn = RoundedButton(
            wrap, text=f"{repo['name']}  ↗", command=lambda: webbrowser.open(html_url) if html_url else None,
            bg_color=GREY_PANEL, hover_color=GREY_BORDER, fg=WHITE_TXT,
            font=(MONO_FONT, 18, "bold"), radius=10, width=420, height=54,
            parent_bg=BLACK, border_color=GREY_BORDER, border_width=1
        )
        name_btn.pack(anchor="w", pady=(0, 6))
        tk.Label(wrap, text="Click the name above to open this repository on GitHub",
                 font=(MONO_FONT, 9), bg=BLACK, fg=GREY_TEXT).pack(anchor="w", pady=(0, 18))

        if repo.get("description"):
            tk.Label(wrap, text=repo["description"], font=(MONO_FONT, 11), bg=BLACK, fg=WHITE_TXT,
                     wraplength=800, justify="left").pack(anchor="w", pady=(0, 22))

        stats = [
            ("⭐ Stars", repo.get("stargazers_count", 0)),
            ("🍴 Forks", repo.get("forks_count", 0)),
            ("👀 Watchers", repo.get("watchers_count", 0)),
            ("🐛 Open issues", repo.get("open_issues_count", 0)),
            ("💾 Size (KB)", repo.get("size", 0)),
            ("🌿 Default branch", repo.get("default_branch", "-")),
        ]
        grid = tk.Frame(wrap, bg=BLACK)
        grid.pack(fill="x", pady=(0, 26))
        for i, (label, value) in enumerate(stats):
            card = tk.Frame(grid, bg=GREY_PANEL, padx=18, pady=14,
                             highlightbackground=GREY_BORDER, highlightthickness=1)
            card.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
            tk.Label(card, text=str(value), font=(MONO_FONT, 14, "bold"), bg=GREY_PANEL, fg=WHITE_TXT).pack()
            tk.Label(card, text=label, font=(MONO_FONT, 9), bg=GREY_PANEL, fg=GREY_TEXT).pack()
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1)

        tk.Label(wrap, text="Language Breakdown", font=(MONO_FONT, 13, "bold"),
                 bg=BLACK, fg=WHITE_TXT).pack(anchor="w", pady=(0, 12))

        self.repo_lang_container = tk.Frame(wrap, bg=BLACK)
        self.repo_lang_container.pack(fill="both", expand=True)
        tk.Label(self.repo_lang_container, text="Loading language data...", font=(MONO_FONT, 10),
                 bg=BLACK, fg=GREY_TEXT).pack(anchor="w")

        owner = (repo.get("owner") or {}).get("login")
        if owner:
            threading.Thread(
                target=self._fetch_repo_languages_thread, args=(owner, repo["name"]), daemon=True
            ).start()
        else:
            self._render_repo_languages_chart({})

    def _fetch_repo_languages_thread(self, owner, repo_name):
        try:
            analyzer = GitHubAnalyzer(owner, token=self.app.token)
            langs = analyzer.fetch_repo_languages(owner, repo_name)
        except Exception:
            langs = {}
        self.after(0, self._render_repo_languages_chart, langs)

    def _render_repo_languages_chart(self, langs):
        for widget in self.repo_lang_container.winfo_children():
            widget.destroy()

        if not langs:
            tk.Label(self.repo_lang_container, text="No language data available for this repository.",
                     font=(MONO_FONT, 10), bg=BLACK, fg=GREY_TEXT).pack(anchor="w")
            return

        fig = Figure(figsize=(5.5, 4), dpi=100, facecolor=BLACK)
        ax = fig.add_subplot(111)
        ax.set_facecolor(GREY_PANEL)
        ax.pie(langs.values(), labels=langs.keys(), autopct="%1.0f%%", startangle=90,
               textprops={"color": WHITE_TXT, "fontfamily": "monospace"})
        ax.set_title("Languages used (by bytes)", color=WHITE_TXT, fontfamily="monospace")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.repo_lang_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # Vivid accent palette (reusing the "bold" tints already defined at the top
    # of the file) used to make both charts pop against the black/grey theme.
    CHART_PALETTE = [ACCENT_GREEN, ACCENT_CYAN, BOLD_PINK, BOLD_PEACH,
                      BOLD_MINT, BOLD_LAVENDER, "#F5D547", "#FF7A7A"]

    def _render_charts(self, data):
        self._clear(self.charts_frame)

        wrap = tk.Frame(self.charts_frame, bg=BLACK)
        wrap.pack(fill="both", expand=True, padx=30, pady=24)

        tk.Label(wrap, text="STATISTICS", font=(MONO_FONT, 20, "bold"),
                 bg=BLACK, fg=WHITE_TXT).pack(anchor="w", pady=(0, 2))
        tk.Label(wrap, text="Language breakdown and top repos at a glance", font=(MONO_FONT, 10),
                 bg=BLACK, fg=GREY_TEXT).pack(anchor="w", pady=(0, 16))

        chart_card = tk.Frame(wrap, bg=GREY_PANEL, highlightbackground=GREY_BORDER,
                               highlightthickness=1)
        chart_card.pack(fill="both", expand=True)

        fig = Figure(figsize=(10, 5), dpi=100, facecolor=GREY_PANEL)
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)
        for ax in (ax1, ax2):
            ax.set_facecolor(GREY_PANEL)

        palette = self.CHART_PALETTE

        # --- Donut-style language breakdown, bold % labels + a clean legend ---
        langs = data["language_breakdown"]
        if langs:
            colors = [palette[i % len(palette)] for i in range(len(langs))]
            wedges, _texts, autotexts = ax1.pie(
                langs.values(), startangle=90, colors=colors,
                autopct=lambda pct: f"{pct:.0f}%" if pct >= 5 else "",
                pctdistance=0.78, wedgeprops={"width": 0.42, "edgecolor": GREY_PANEL, "linewidth": 2},
            )
            for at in autotexts:
                at.set_color(BLACK)
                at.set_fontfamily("monospace")
                at.set_fontweight("bold")
                at.set_fontsize(10)
            ax1.set_title("LANGUAGE BREAKDOWN", color=WHITE_TXT, fontfamily="monospace",
                           fontweight="bold", fontsize=13, pad=14)
            ax1.legend(
                wedges, langs.keys(), loc="center left", bbox_to_anchor=(1.02, 0.5),
                frameon=False, labelcolor=WHITE_TXT, prop={"family": "monospace", "weight": "bold", "size": 9},
            )
        else:
            ax1.text(0.5, 0.5, "No language data", ha="center", va="center",
                     color=GREY_TEXT, fontfamily="monospace", fontweight="bold")
            ax1.axis("off")

        # --- Bold horizontal bar chart with value labels at the end of each bar ---
        top_repos = data["top_repos"][:5]
        if top_repos:
            names = [r["name"] for r in top_repos][::-1]
            stars = [r.get("stargazers_count", 0) for r in top_repos][::-1]
            bar_colors = [palette[i % len(palette)] for i in range(len(names))]
            bars = ax2.barh(names, stars, color=bar_colors, height=0.6,
                             edgecolor=BLACK, linewidth=0.8)
            ax2.set_title("TOP REPOS BY STARS", color=WHITE_TXT, fontfamily="monospace",
                           fontweight="bold", fontsize=13, pad=14)
            ax2.tick_params(colors=WHITE_TXT)
            ax2.set_xticks([])
            for spine in ax2.spines.values():
                spine.set_visible(False)
            for label in ax2.get_yticklabels():
                label.set_fontfamily("monospace")
                label.set_fontweight("bold")
                label.set_fontsize(10)
            max_star = max(stars) if stars else 1
            for bar, val in zip(bars, stars):
                ax2.text(bar.get_width() + max_star * 0.02, bar.get_y() + bar.get_height() / 2,
                          f"⭐ {val:,}", va="center", ha="left", color=WHITE_TXT,
                          fontfamily="monospace", fontweight="bold", fontsize=10)
            ax2.set_xlim(0, max_star * 1.22)
        else:
            ax2.text(0.5, 0.5, "No repos found", ha="center", va="center",
                      color=GREY_TEXT, fontfamily="monospace", fontweight="bold")
            ax2.axis("off")

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=GREY_PANEL, highlightthickness=0)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=20)


if __name__ == "__main__":
    app = GitHubAnalyzerApp()
    app.mainloop()
