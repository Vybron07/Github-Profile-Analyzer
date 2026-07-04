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

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
            self.after(0, self._on_fetch_success, data)
        except GitHubAPIError as e:
            self.after(0, self._on_fetch_error, str(e))
        except Exception as e:
            self.after(0, self._on_fetch_error, f"Unexpected error: {e}")

    def _on_fetch_success(self, data):
        self.data = data
        self._save_recent_search(self.username)
        self.show_screen(ResultsScreen)

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
        self.token_visible = False
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

        tk.Label(form_wrap, text="$ Analyze --user", font=(MONO_FONT, 20, "bold"),
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
        username_canvas.pack(anchor="w", pady=(0, 18))
        self.username_entry.insert(0, "octocat")
        self.username_entry.bind("<Return>", lambda e: self.on_analyze())

        tk.Label(form_wrap, text="ACCESS TOKEN (OPTIONAL)", font=(MONO_FONT, 9, "bold"),
                 bg=DARK_PANEL, fg=TEXT_DIM).pack(anchor="w", pady=(0, 4))
        token_row = tk.Frame(form_wrap, bg=DARK_PANEL)
        token_row.pack(anchor="w", pady=(0, 18))
        token_canvas, self.token_entry = make_rounded_entry(
            token_row, width_px=278, height_px=46, radius=23, show="*", fill=DARK_BG,
            border=DARK_BORDER, font=(MONO_FONT, 12)
        )
        self.token_entry.config(fg=TEXT_LIGHT, insertbackground=ACCENT_GREEN)
        token_canvas.pack(side="left")
        self.token_toggle_btn = RoundedButton(
            token_row, text="Show", command=self._toggle_token_visibility,
            bg_color=DARK_BG, hover_color=DARK_BORDER, fg=ACCENT_CYAN,
            font=(MONO_FONT, 9, "bold"), radius=23, width=54, height=46,
            parent_bg=DARK_PANEL, border_color=DARK_BORDER, border_width=1
        )
        self.token_toggle_btn.pack(side="left", padx=(8, 0))

        topn_row = tk.Frame(form_wrap, bg=DARK_PANEL)
        topn_row.pack(anchor="w", pady=(0, 26))
        tk.Label(topn_row, text="Top repos:", font=(MONO_FONT, 10), bg=DARK_PANEL, fg=TEXT_LIGHT).pack(side="left")
        self.top_n_var = tk.StringVar(value="5")
        ttk.Spinbox(topn_row, from_=1, to=20, width=5, textvariable=self.top_n_var).pack(side="left", padx=(8, 0))

        self.analyze_btn = RoundedButton(
            form_wrap, text="▶  Run Analysis", command=self.on_analyze,
            bg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER, fg=DARK_BG,
            font=(MONO_FONT, 13, "bold"), radius=27, width=340, height=54, parent_bg=DARK_PANEL
        )
        self.analyze_btn.pack(anchor="w")

        tk.Label(form_wrap, text="# Tip: add a token to raise rate limit 60 -> 5,000 req/hr",
                 font=(MONO_FONT, 8), bg=DARK_PANEL, fg=TEXT_DIM, wraplength=340, justify="left").pack(
            anchor="w", pady=(10, 0)
        )

        self.recent_label = tk.Label(form_wrap, text="RECENT", font=(MONO_FONT, 9, "bold"),
                                      bg=DARK_PANEL, fg=TEXT_DIM)
        self.recent_frame = tk.Frame(form_wrap, bg=DARK_PANEL)

        self.form_wrap = form_wrap

    # ------------------------------------------------------------------
    def _toggle_token_visibility(self):
        self.token_visible = not self.token_visible
        self.token_entry.config(show="" if self.token_visible else "*")
        self.token_toggle_btn.set_text("Hide" if self.token_visible else "Show")

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
        try:
            top_n = int(self.top_n_var.get())
        except ValueError:
            top_n = 5

        token = self.token_entry.get().strip()
        self.app.start_analysis(username, token, top_n)


# =======================================================================
# SCREEN 2: Loading
# =======================================================================
class LoadingScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

        center = tk.Frame(self, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="🐙", font=("Segoe UI", 48), bg=BG).pack(pady=(0, 8))

        self.status_var = tk.StringVar(value="Fetching data...")
        tk.Label(center, textvariable=self.status_var, font=FONT_SUBTITLE, bg=BG, fg=TEXT_DARK).pack(pady=(0, 16))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Pastel.Horizontal.TProgressbar", troughcolor=CARD, background=BTN_PRIMARY, thickness=10)

        self.progress = ttk.Progressbar(
            center, style="Pastel.Horizontal.TProgressbar", mode="indeterminate", length=280
        )
        self.progress.pack()

    def on_show(self):
        self.status_var.set(f"Fetching data for '{self.app.username}'...")
        self.progress.start(12)

    def on_hide(self):
        self.progress.stop()


# =======================================================================
# SCREEN 3: Results
# =======================================================================
class ResultsScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

        header = tk.Frame(self, bg=LAVENDER, height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        self.header_label = tk.Label(header, text="", font=("Segoe UI", 16, "bold"), bg=LAVENDER, fg=TEXT_DARK)
        self.header_label.pack(side="left", padx=24, pady=10)

        back_btn = tk.Button(
            header, text="← New Search", font=FONT_BODY_BOLD, bg=CARD, fg=TEXT_DARK,
            relief="flat", padx=16, pady=6, cursor="hand2", command=self.on_back
        )
        back_btn.pack(side="right", padx=24, pady=10)

        style = ttk.Style()
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=FONT_BODY_BOLD, padding=[16, 8], background=PEACH, foreground=TEXT_DARK)
        style.map("TNotebook.Tab", background=[("selected", CARD)])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=24)

        self.overview_frame = tk.Frame(self.notebook, bg=CARD)
        self.repos_frame = tk.Frame(self.notebook, bg=CARD)
        self.charts_frame = tk.Frame(self.notebook, bg=CARD)

        self.notebook.add(self.overview_frame, text="Overview")
        self.notebook.add(self.repos_frame, text="Top Repos")
        self.notebook.add(self.charts_frame, text="Charts")

    def on_back(self):
        self.app.show_screen(HomeScreen)

    def on_show(self):
        data = self.app.data
        if not data:
            return
        self.app.frames[LoadingScreen].on_hide()
        self.header_label.config(text=f"{data['name'] or data['username']}  (@{data['username']})")
        self._render_overview(data)
        self._render_repos(data)
        self._render_charts(data)

    # ------------------------------------------------------------------
    def _clear(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def _render_overview(self, data):
        self._clear(self.overview_frame)
        wrap = tk.Frame(self.overview_frame, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=30, pady=24)

        if data["bio"]:
            tk.Label(wrap, text=data["bio"], font=FONT_BODY, bg=CARD, fg=TEXT_DARK,
                     wraplength=700, justify="left").pack(anchor="w", pady=(0, 8))

        stats_frame = tk.Frame(wrap, bg=CARD)
        stats_frame.pack(fill="x", pady=12)

        stat_cards = [
            ("Followers", data["followers"], SKY),
            ("Following", data["following"], PEACH),
            ("Public repos", data["public_repos"], MINT),
            ("Total stars", data["total_stars"], PINK),
            ("Total forks", data["total_forks"], LAVENDER),
            ("Account age (yrs)", data["account_age_years"], SKY),
        ]
        for i, (label, value, color) in enumerate(stat_cards):
            card = tk.Frame(stats_frame, bg=color, padx=18, pady=14)
            card.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
            tk.Label(card, text=str(value), font=("Segoe UI", 16, "bold"), bg=color, fg=TEXT_DARK).pack()
            tk.Label(card, text=label, font=FONT_BODY, bg=color, fg=TEXT_DARK).pack()

        for c in range(3):
            stats_frame.grid_columnconfigure(c, weight=1)

        if data["location"]:
            tk.Label(wrap, text=f"📍 {data['location']}", font=FONT_BODY, bg=CARD, fg=TEXT_MUTED).pack(anchor="w")

    def _render_repos(self, data):
        self._clear(self.repos_frame)
        wrap = tk.Frame(self.repos_frame, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=30, pady=24)

        tk.Label(wrap, text="Top repositories by stars", font=FONT_HEADING, bg=CARD, fg=TEXT_DARK).pack(
            anchor="w", pady=(0, 12)
        )

        columns = ("name", "stars", "forks", "description")
        tree = ttk.Treeview(wrap, columns=columns, show="headings", height=12)
        tree.heading("name", text="Repository")
        tree.heading("stars", text="⭐ Stars")
        tree.heading("forks", text="🍴 Forks")
        tree.heading("description", text="Description")
        tree.column("name", width=160)
        tree.column("stars", width=80, anchor="center")
        tree.column("forks", width=80, anchor="center")
        tree.column("description", width=380)

        for repo in data["top_repos"][: self.app.top_n]:
            tree.insert("", "end", values=(
                repo["name"],
                repo.get("stargazers_count", 0),
                repo.get("forks_count", 0),
                (repo.get("description") or "")[:80],
            ))

        tree.pack(fill="both", expand=True)

    def _render_charts(self, data):
        self._clear(self.charts_frame)

        fig = Figure(figsize=(9, 4.5), dpi=100, facecolor=CARD)
        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)

        langs = data["language_breakdown"]
        if langs:
            ax1.pie(langs.values(), labels=langs.keys(), autopct="%1.0f%%", startangle=90)
            ax1.set_title("Language Breakdown")
        else:
            ax1.text(0.5, 0.5, "No language data", ha="center", va="center")

        top_repos = data["top_repos"][:5]
        if top_repos:
            names = [r["name"] for r in top_repos]
            stars = [r.get("stargazers_count", 0) for r in top_repos]
            ax2.barh(names[::-1], stars[::-1], color="#B9A6E8")
            ax2.set_title("Top Repos by Stars")
            ax2.set_xlabel("Stars")
        else:
            ax2.text(0.5, 0.5, "No repos found", ha="center", va="center")

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.charts_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=20)


if __name__ == "__main__":
    app = GitHubAnalyzerApp()
    app.mainloop()
