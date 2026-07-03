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

# Extra-light tints used only for the background doodle cluster
DOODLE_COLORS = ["#F3ECFB", "#FCE9F1", "#E9F8EF", "#EAF4FD", "#FDF0E6"]

RECENT_SEARCHES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recent_searches.json")
MAX_RECENT = 6

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
        self.geometry("980x680")
        self.configure(bg=BG)
        self.minsize(820, 600)

        # Shared state passed between screens
        self.username = ""
        self.token = ""
        self.top_n = 5
        self.data = None
        self.recent_searches = self._load_recent_searches()

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
    """Split-screen layout: vibrant gradient brand panel on the left,
    clean white form panel on the right."""

    LEFT_FRAC = 42  # left panel width as a percentage (grid weight)
    RIGHT_FRAC = 58

    def __init__(self, parent, app):
        super().__init__(parent, bg=CARD)
        self.app = app
        self.token_visible = False

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=self.LEFT_FRAC)
        self.grid_columnconfigure(1, weight=self.RIGHT_FRAC)

        # ---------------- LEFT: brand / illustration panel ----------------
        self.left_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_canvas.bind("<Configure>", self._draw_left_panel)

        # ---------------- RIGHT: form panel ----------------
        right = tk.Frame(self, bg=CARD)
        right.grid(row=0, column=1, sticky="nsew")

        form_wrap = tk.Frame(right, bg=CARD)
        form_wrap.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form_wrap, text="Welcome back", font=("Segoe UI", 22, "bold"),
                 bg=CARD, fg=TEXT_DARK).pack(anchor="w")
        tk.Label(form_wrap, text="Analyze any public GitHub profile in seconds",
                 font=("Segoe UI", 11), bg=CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(2, 28))

        tk.Label(form_wrap, text="GITHUB USERNAME", font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        self.username_entry = ttk.Entry(form_wrap, font=("Segoe UI", 13), width=30)
        self.username_entry.pack(anchor="w", ipady=4, pady=(0, 18))
        self.username_entry.insert(0, "octocat")
        self.username_entry.bind("<Return>", lambda e: self.on_analyze())

        tk.Label(form_wrap, text="PERSONAL ACCESS TOKEN (OPTIONAL)", font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        token_row = tk.Frame(form_wrap, bg=CARD)
        token_row.pack(anchor="w", pady=(0, 18))
        self.token_entry = ttk.Entry(token_row, font=("Segoe UI", 13), width=25, show="*")
        self.token_entry.pack(side="left", ipady=4)
        self.token_toggle_btn = tk.Button(
            token_row, text="👁", font=("Segoe UI", 10), bg=PEACH, fg=TEXT_DARK, relief="flat",
            width=3, cursor="hand2", command=self._toggle_token_visibility
        )
        self.token_toggle_btn.pack(side="left", padx=(6, 0), ipady=2)

        topn_row = tk.Frame(form_wrap, bg=CARD)
        topn_row.pack(anchor="w", pady=(0, 26))
        tk.Label(topn_row, text="Top repos to show:", font=FONT_BODY, bg=CARD, fg=TEXT_DARK).pack(side="left")
        self.top_n_var = tk.StringVar(value="5")
        ttk.Spinbox(topn_row, from_=1, to=20, width=5, textvariable=self.top_n_var).pack(side="left", padx=(8, 0))

        self.analyze_btn = tk.Button(
            form_wrap, text="Analyze Profile  →", font=("Segoe UI", 12, "bold"), bg=BTN_PRIMARY, fg="white",
            activebackground=BTN_PRIMARY_HOVER, relief="flat", padx=28, pady=12,
            cursor="hand2", command=self.on_analyze
        )
        self.analyze_btn.pack(anchor="w", fill="x")
        self.analyze_btn.bind("<Enter>", lambda e: self.analyze_btn.config(bg=BTN_PRIMARY_HOVER))
        self.analyze_btn.bind("<Leave>", lambda e: self.analyze_btn.config(bg=BTN_PRIMARY))

        tk.Label(form_wrap, text="Tip: add a token to raise your rate limit from 60 to 5,000 requests/hour",
                 font=("Segoe UI", 8), bg=CARD, fg=TEXT_MUTED, wraplength=320, justify="left").pack(
            anchor="w", pady=(10, 0)
        )

        self.recent_label = tk.Label(form_wrap, text="RECENT SEARCHES", font=("Segoe UI", 9, "bold"),
                                      bg=CARD, fg=TEXT_MUTED)
        self.recent_frame = tk.Frame(form_wrap, bg=CARD)

        self.form_wrap = form_wrap

    # ------------------------------------------------------------------
    def _toggle_token_visibility(self):
        self.token_visible = not self.token_visible
        self.token_entry.config(show="" if self.token_visible else "*")
        self.token_toggle_btn.config(text="🙈" if self.token_visible else "👁")

    # ------------------------------------------------------------------
    # Left panel: gradient background + doodle illustration + copy
    # ------------------------------------------------------------------
    @staticmethod
    def _lerp_color(c1, c2, t):
        c1 = c1.lstrip("#")
        c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = round(r1 + (r2 - r1) * t)
        g = round(g1 + (g2 - g1) * t)
        b = round(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _draw_left_panel(self, event=None):
        c = self.left_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return

        # Diagonal-feeling vertical gradient: lavender -> pink -> peach
        steps = 60
        for i in range(steps):
            t = i / steps
            if t < 0.5:
                color = self._lerp_color(LAVENDER, PINK, t * 2)
            else:
                color = self._lerp_color(PINK, PEACH, (t - 0.5) * 2)
            y0 = h * i / steps
            y1 = h * (i + 1) / steps
            c.create_rectangle(0, y0, w, y1 + 1, fill=color, outline="")

        # Big badge icon
        badge_r = 46
        bx, by = w * 0.5, h * 0.20
        c.create_oval(bx - badge_r, by - badge_r, bx + badge_r, by + badge_r,
                       fill="#FFFFFF", outline="")
        c.create_text(bx, by, text="🐙", font=("Segoe UI", 38))

        c.create_text(w * 0.5, h * 0.34, text="GitHub Profile\nAnalyzer",
                       font=("Segoe UI", 22, "bold"), fill=TEXT_DARK, justify="center")
        c.create_text(w * 0.5, h * 0.42, text="Deep-dive into any public profile",
                       font=("Segoe UI", 10), fill=TEXT_DARK, justify="center")

        # Feature list
        features = [
            "⭐  Ranked top repositories",
            "🧩  Language breakdown",
            "📊  Visual charts",
            "⚡  Fast, no login required",
        ]
        start_y = h * 0.55
        for i, feat in enumerate(features):
            c.create_text(w * 0.5, start_y + i * 34, text=feat, font=("Segoe UI", 11),
                           fill=TEXT_DARK, anchor="center")

        # Decorative doodles scattered around the edges (kept clear of text)
        self._draw_star(c, w * 0.15, h * 0.10, 10, "#FFFFFF")
        self._draw_star(c, w * 0.85, h * 0.08, 7, "#FFFFFF")
        self._draw_star(c, w * 0.90, h * 0.62, 9, "#FFFFFF")
        self._draw_star(c, w * 0.12, h * 0.88, 8, "#FFFFFF")
        self._draw_commit_trail(c, w * 0.68, h * 0.90, "#FFFFFF")
        for fx, fy, r in [(0.08, 0.5, 4), (0.92, 0.35, 5), (0.2, 0.7, 3), (0.8, 0.15, 4)]:
            x, y = w * fx, h * fy
            c.create_oval(x - r, y - r, x + r, y + r, fill="#FFFFFF", outline="")

    def _draw_star(self, c, cx, cy, size, color):
        points = []
        for i in range(10):
            angle = math.pi / 5 * i - math.pi / 2
            r = size if i % 2 == 0 else size * 0.45
            points.append(cx + r * math.cos(angle))
            points.append(cy + r * math.sin(angle))
        c.create_polygon(points, fill=color, outline="")

    def _draw_commit_trail(self, c, x, y, color):
        for i in range(4):
            cx = x + i * 20
            cy = y + (i % 2) * 14
            c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=color, outline="")
            if i > 0:
                px = x + (i - 1) * 20
                py = y + ((i - 1) % 2) * 14
                c.create_line(px, py, cx, cy, fill=color, width=2)

    # ------------------------------------------------------------------
    def on_show(self):
        self.username_entry.focus_set()
        self._refresh_recent_chips()
        self.after(50, self._draw_left_panel)

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
            chip = tk.Button(
                self.recent_frame, text=username, font=("Segoe UI", 9), bg=SKY, fg=TEXT_DARK,
                relief="flat", padx=12, pady=5, cursor="hand2",
                command=lambda u=username: self._use_recent(u)
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
