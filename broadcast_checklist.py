#!/usr/bin/env python3
"""
Broadcast Checklist
Full-day grid view for hourly on-air status tracking.
Broadcast day: 5:00 AM through 4:59 AM.
Database: broadcast_log.db (SQLite, created automatically beside this file).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
import os
import sys as _sys

# ── Station configuration ──────────────────────────────────────────────────────
STATIONS = [
    {"id": "WICS", "network": "ABC",    "substations": ["CHARGE!", "Comet TV", "ROAR"]},
    {"id": "WICD", "network": "ABC",    "substations": ["CHARGE!", "Comet TV", "ROAR"]},
    {"id": "WRSP", "network": "FOX",    "substations": ["True Crime Network", "Antenna TV"]},
    {"id": "WCCU", "network": "FOX",    "substations": ["True Crime Network", "Antenna TV"]},
    {"id": "WBUI", "network": "The CW", "substations": ["Dabl", "The Nest", "Rewind TV"]},
]

SHORT_LABEL = {
    "ABC": "ABC", "FOX": "FOX", "The CW": "CW",
    "CHARGE!": "Charge", "Comet TV": "Comet", "ROAR": "ROAR",
    "True Crime Network": "TC", "Antenna TV": "Ant",
    "Dabl": "Dabl", "The Nest": "Nest", "Rewind TV": "RWTV",
}

# Build ordered column list and station group spans
CHANNEL_COLS  = []   # [(channel_key, short_label), ...]
STATION_SPANS = []   # [(station_id, colspan, start_col), ...]
_col = 1
for _s in STATIONS:
    _start = _col
    CHANNEL_COLS.append((f"{_s['id']}__main", SHORT_LABEL.get(_s['network'], _s['network'])))
    _col += 1
    for _sub in _s['substations']:
        CHANNEL_COLS.append((f"{_s['id']}__{_sub}", SHORT_LABEL.get(_sub, _sub)))
        _col += 1
    STATION_SPANS.append((_s['id'], _col - _start, _start))

COL_TIME      = 0
COL_CHAN_START = 1
COL_EMPLOYEE  = COL_CHAN_START + len(CHANNEL_COLS)       # 19
COL_SIGNOFF   = COL_CHAN_START + len(CHANNEL_COLS) + 1   # 20

BROADCAST_START_HOUR = 5
BCAST_HOURS  = list(range(BROADCAST_START_HOUR, 24)) + list(range(0, BROADCAST_START_HOUR))
HOUR_LABELS  = [datetime.time(h, 0).strftime("%I:%M %p").lstrip("0") for h in BCAST_HOURS]

# Database path (works both as .py and PyInstaller .exe)
if getattr(_sys, "frozen", False):
    _app_dir = os.path.dirname(_sys.executable)
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_app_dir, "broadcast_log.db")

# ── Colour palette ─────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
BG_CARD   = "#313244"
BG_HDR    = "#181825"
BG_ROW_A  = "#2a2a3c"
BG_ROW_B  = "#252535"
BG_CUR    = "#3d3d5c"
BG_BORDER = "#0f0f1a"
BLUE      = "#89b4fa"
GREEN     = "#a6e3a1"
RED       = "#f38ba8"
YELLOW    = "#f9e2af"
TEXT      = "#cdd6f4"
SUBTEXT   = "#a6adc8"
DIM       = "#585b70"


def font(size, bold=False):
    return ("Segoe UI", size, "bold" if bold else "normal")


# ── Database ───────────────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS signoffs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                broadcast_date TEXT    NOT NULL,
                hour           INTEGER NOT NULL,
                operator_name  TEXT    NOT NULL,
                notes          TEXT    NOT NULL DEFAULT '',
                signed_off_at  TEXT    NOT NULL,
                UNIQUE(broadcast_date, hour)
            );
            CREATE TABLE IF NOT EXISTS channel_status (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                signoff_id  INTEGER NOT NULL REFERENCES signoffs(id),
                channel_key TEXT    NOT NULL,
                on_air      INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS operators (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE COLLATE NOCASE
            );
        """)


def broadcast_date(dt):
    """Return broadcast date for a datetime (day starts at 5 AM)."""
    if dt.hour < BROADCAST_START_HOUR:
        return (dt - datetime.timedelta(days=1)).date()
    return dt.date()


def get_signoff(bdate, hour):
    with sqlite3.connect(DB_PATH) as c:
        return c.execute(
            "SELECT id, operator_name, notes, signed_off_at "
            "FROM signoffs WHERE broadcast_date=? AND hour=?",
            (str(bdate), hour)
        ).fetchone()


def get_statuses(signoff_id):
    """Returns {channel_key: int} where int is 0=Unknown, 1=On Air, 2=Off Air."""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            "SELECT channel_key, on_air FROM channel_status WHERE signoff_id=?",
            (signoff_id,)
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def save_signoff(bdate, hour, operator, notes, statuses):
    now = datetime.datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO signoffs (broadcast_date, hour, operator_name, notes, signed_off_at) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(broadcast_date, hour) DO UPDATE SET "
            "operator_name=excluded.operator_name, notes=excluded.notes, "
            "signed_off_at=excluded.signed_off_at",
            (str(bdate), hour, operator, notes, now),
        )
        sid = c.execute(
            "SELECT id FROM signoffs WHERE broadcast_date=? AND hour=?",
            (str(bdate), hour)
        ).fetchone()[0]
        c.execute("DELETE FROM channel_status WHERE signoff_id=?", (sid,))
        c.executemany(
            "INSERT INTO channel_status (signoff_id, channel_key, on_air) VALUES (?,?,?)",
            [(sid, k, int(v)) for k, v in statuses.items()],
        )


def get_operators():
    with sqlite3.connect(DB_PATH) as c:
        return [r[0] for r in c.execute(
            "SELECT name FROM operators ORDER BY name COLLATE NOCASE"
        ).fetchall()]


def add_operator(name):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT OR IGNORE INTO operators (name) VALUES (?)", (name.strip(),))


def remove_operator(name):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM operators WHERE name=?", (name,))


def rename_operator(old_name, new_name):
    """Rename an operator without touching any historical sign-off records."""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE operators SET name=? WHERE name=?",
                  (new_name.strip(), old_name))


def get_previous_row_statuses(view_date, hour_idx):
    """Return statuses from the closest signed row before hour_idx.
    Falls back to the previous broadcast day's last signed row if needed."""
    for i in range(hour_idx - 1, -1, -1):
        row = get_signoff(view_date, BCAST_HOURS[i])
        if row:
            return get_statuses(row[0])
    prev = view_date - datetime.timedelta(days=1)
    for hour in reversed(BCAST_HOURS):
        row = get_signoff(prev, hour)
        if row:
            return get_statuses(row[0])
    return None


# ── ThreeStateCell ─────────────────────────────────────────────────────────────
# States: 0 = Unknown (□), 1 = On Air (✔), 2 = Off Air (✘)
_CELL_CFG = {
    0: ("□",  SUBTEXT,  None),
    1: ("✔",  GREEN,    "#1a3328"),
    2: ("✘",  RED,      "#331a1a"),
}


class ThreeStateCell(tk.Label):
    def __init__(self, parent, var, row_bg, readonly=False, **kw):
        self._var    = var
        self._row_bg = row_bg
        super().__init__(parent, font=font(10, bold=True), anchor="center",
                         padx=3, pady=2, **kw)
        self._refresh()
        # React immediately when var is set externally (e.g. copy-previous-row)
        self._var.trace_add("write", lambda *_: self.after_idle(self._refresh))
        if not readonly:
            self.bind("<Button-1>", self._cycle)
            self.config(cursor="hand2")

    def _cycle(self, _=None):
        self._var.set((self._var.get() + 1) % 3)
        self._refresh()

    def _refresh(self):
        sym, fg, bg = _CELL_CFG[self._var.get()]
        self.config(text=sym, fg=fg, bg=bg if bg else self._row_bg)


# ── ScrollFrame ────────────────────────────────────────────────────────────────
class ScrollFrame(tk.Frame):
    def __init__(self, parent, expand_width=True, **kw):
        bg = kw.get("bg", BG)
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.sb     = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner  = tk.Frame(self.canvas, bg=bg)
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self._win_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        if expand_width:
            self.canvas.bind(
                "<Configure>",
                lambda e: self.canvas.itemconfig(self._win_id, width=e.width)
            )
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_wheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _bind_wheel(self, _):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>",   self._on_wheel)
        self.canvas.bind_all("<Button-5>",   self._on_wheel)

    def _unbind_wheel(self, _):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")


# ── Main Application ───────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Broadcast Checklist")
        self.geometry("1280x760")
        self.minsize(900, 520)
        self.configure(bg=BG)

        init_db()
        self._editing_hours = set()
        self._view_date     = None
        self._last_hour     = -1

        self._build_header()
        self._build_nav()
        self.bind("<Control-o>", lambda _: self.show_operators())

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.content.columnconfigure(0, weight=1)

        self.show_day_view()
        self._tick()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HDR, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Broadcast Checklist",
                 font=font(17, bold=True), fg=TEXT, bg=BG_HDR).pack(side="left", padx=20)
        self._lbl_time  = tk.Label(hdr, text="", font=font(13), fg=BLUE,   bg=BG_HDR)
        self._lbl_time.pack(side="right", padx=16)
        self._lbl_bdate = tk.Label(hdr, text="", font=font(10), fg=SUBTEXT, bg=BG_HDR)
        self._lbl_bdate.pack(side="right", padx=4)

    def _tick(self):
        now = datetime.datetime.now()
        bd  = broadcast_date(now)
        self._lbl_time.config(text=now.strftime("%I:%M %p"))
        self._lbl_bdate.config(text=f"Broadcast Date: {bd.strftime('%A, %B %d, %Y')}")
        if (self._view_date == bd) and (now.hour != self._last_hour) and (self._last_hour != -1):
            self.show_day_view(self._view_date)
        self._last_hour = now.hour
        self.after(10_000, self._tick)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _build_nav(self):
        nav = tk.Frame(self, bg=BG, pady=8)
        nav.pack(fill="x", padx=20)
        self._btn_check = tk.Button(
            nav, text="Checklist",
            command=lambda: self.show_day_view(self._view_date),
            font=font(11, bold=True), bg=BLUE, fg=BG,
            relief="flat", padx=16, pady=6, cursor="hand2",
        )
        self._btn_check.pack(side="left")

    def _nav_select(self, which):
        if which == "check":
            self._btn_check.config(bg=BLUE, fg=BG, font=font(11, bold=True))
        else:
            self._btn_check.config(bg=BG_CARD, fg=TEXT, font=font(11))

    def _clear(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.content.rowconfigure(0, weight=0)
        self.content.rowconfigure(1, weight=1)

    # ── Day view ──────────────────────────────────────────────────────────────
    def show_day_view(self, view_date=None):
        self._nav_select("check")
        self._clear()

        today     = broadcast_date(datetime.datetime.now())
        yesterday = today - datetime.timedelta(days=1)
        if view_date is None:
            view_date = today
        self._view_date = view_date
        is_today    = (view_date == today)
        is_editable = (view_date >= yesterday)   # today and yesterday are editable

        # Date navigation bar
        nav_bar = tk.Frame(self.content, bg=BG_HDR, pady=6)
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.columnconfigure(1, weight=1)

        tk.Button(
            nav_bar, text="◀", command=self._prev_day,
            font=font(13), bg=BG_HDR, fg=TEXT, relief="flat",
            padx=14, pady=2, cursor="hand2", activebackground=BG_CARD,
        ).grid(row=0, column=0, padx=(14, 4))

        date_lbl = tk.Label(
            nav_bar, text=view_date.strftime("%A, %B %d, %Y"),
            font=font(13, bold=True), fg=BLUE, bg=BG_HDR, cursor="hand2",
        )
        date_lbl.grid(row=0, column=1)
        date_lbl.bind("<Button-1>", self._open_date_picker)

        tk.Button(
            nav_bar, text="▶", command=self._next_day,
            font=font(13),
            bg=BG_HDR, fg=(DIM if is_today else TEXT),
            relief="flat", padx=14, pady=2,
            cursor=("" if is_today else "hand2"),
            state=("disabled" if is_today else "normal"),
            activebackground=BG_CARD,
        ).grid(row=0, column=2, padx=(4, 14))

        # Non-scrolling grid that expands to fill the window
        self.content.rowconfigure(1, weight=1)
        grid_frame = tk.Frame(self.content, bg=BG_BORDER)
        grid_frame.grid(row=1, column=0, sticky="nsew")

        self._build_grid(grid_frame, view_date, is_today, is_editable)

    def _build_grid(self, parent, view_date, is_today, is_editable):
        now_hour  = datetime.datetime.now().hour
        operators = get_operators()

        # Column weights — all columns share available width proportionally
        parent.columnconfigure(COL_TIME, weight=0, minsize=64)
        for c in range(COL_CHAN_START, COL_EMPLOYEE):
            parent.columnconfigure(c, weight=1, minsize=40)
        parent.columnconfigure(COL_EMPLOYEE, weight=3, minsize=115)
        parent.columnconfigure(COL_SIGNOFF,  weight=0, minsize=80)

        # Row weights — headers are compact; 24 data rows share all remaining height
        parent.rowconfigure(0, weight=0, minsize=20)
        parent.rowconfigure(1, weight=0, minsize=18)
        for i in range(2, 2 + len(BCAST_HOURS)):
            parent.rowconfigure(i, weight=1, minsize=20)

        hkw = dict(bg=BG_HDR, fg=TEXT, padx=2, pady=3, relief="flat")

        # Header row 0 — station group names
        tk.Label(parent, text="Time", font=font(9, bold=True), **hkw).grid(
            row=0, column=COL_TIME, sticky="nsew", padx=1, pady=1)
        for stn_id, span, start in STATION_SPANS:
            tk.Label(parent, text=stn_id, font=font(9, bold=True), **hkw).grid(
                row=0, column=start, columnspan=span, sticky="nsew", padx=1, pady=1)
        tk.Label(parent, text="Employee", font=font(9, bold=True), **hkw).grid(
            row=0, column=COL_EMPLOYEE, sticky="nsew", padx=1, pady=1)
        tk.Label(parent, text="", bg=BG_HDR).grid(
            row=0, column=COL_SIGNOFF, sticky="nsew", padx=1, pady=1)

        # Header row 1 — sub-channel names
        tk.Label(parent, text="", **hkw).grid(
            row=1, column=COL_TIME, sticky="nsew", padx=1, pady=1)
        for i, (_, short) in enumerate(CHANNEL_COLS):
            tk.Label(parent, text=short, font=font(8), **hkw).grid(
                row=1, column=COL_CHAN_START + i, sticky="nsew", padx=1, pady=1)
        tk.Label(parent, text="", **hkw).grid(
            row=1, column=COL_EMPLOYEE, sticky="nsew", padx=1, pady=1)
        tk.Label(parent, text="", bg=BG_HDR).grid(
            row=1, column=COL_SIGNOFF, sticky="nsew", padx=1, pady=1)

        self._row_vars   = {}
        self._row_op_var = {}

        for row_idx, hour in enumerate(BCAST_HOURS):
            grid_row         = row_idx + 2
            is_current       = is_today and (hour == now_hour)
            row_bg           = BG_CUR if is_current else (BG_ROW_A if row_idx % 2 == 0 else BG_ROW_B)
            edit_mode        = hour in self._editing_hours
            existing         = get_signoff(view_date, hour)
            effective_signed = (existing is not None) and not edit_mode
            prior            = get_statuses(existing[0]) if existing else {}
            readonly_cell    = effective_signed or not is_editable

            ckw = dict(bg=row_bg, relief="flat")

            # Time label — clicking on an editable unsigned row copies the previous row
            hour_str  = datetime.time(hour, 0).strftime("%I:%M %p").lstrip("0")
            time_lbl  = tk.Label(parent, text=hour_str, font=font(9, bold=is_current),
                                 fg=(BLUE if is_current else TEXT),
                                 anchor="center", padx=4, **ckw)
            time_lbl.grid(row=grid_row, column=COL_TIME, sticky="nsew", padx=1, pady=1)
            if is_editable and not effective_signed:
                time_lbl.config(cursor="hand2")
                time_lbl.bind("<Button-1>",
                              lambda _e, h=hour, idx=row_idx: self._copy_prev_row(h, idx))

            # Channel cells
            self._row_vars[hour] = {}
            for i, (chan_key, _) in enumerate(CHANNEL_COLS):
                var = tk.IntVar(value=prior.get(chan_key, 0))
                self._row_vars[hour][chan_key] = var
                ThreeStateCell(parent, var, row_bg=row_bg, readonly=readonly_cell).grid(
                    row=grid_row, column=COL_CHAN_START + i,
                    sticky="nsew", padx=1, pady=1)

            # Employee + sign-off columns
            if effective_signed:
                tk.Label(parent, text=existing[1],
                         font=font(9), fg=GREEN, anchor="w", padx=4, **ckw).grid(
                    row=grid_row, column=COL_EMPLOYEE, sticky="nsew", padx=1, pady=1)
                if is_editable:
                    tk.Button(parent, text="Edit",
                              command=lambda h=hour: self._edit_row(h),
                              font=font(9), bg="#263326", fg=GREEN,
                              relief="flat", cursor="hand2", padx=6).grid(
                        row=grid_row, column=COL_SIGNOFF,
                        sticky="nsew", padx=2, pady=2)
                else:
                    tk.Label(parent, text="", **ckw).grid(
                        row=grid_row, column=COL_SIGNOFF, sticky="nsew", padx=1, pady=1)

            elif is_editable:
                if operators:
                    # No default selection — operator must actively choose
                    op_var = tk.StringVar(value="")
                    if edit_mode and existing and existing[1] in operators:
                        op_var.set(existing[1])
                    self._row_op_var[hour] = op_var
                    ttk.Combobox(parent, textvariable=op_var, values=operators,
                                 state="readonly", font=font(9)).grid(
                        row=grid_row, column=COL_EMPLOYEE,
                        sticky="ew", padx=2, pady=3)
                    tk.Button(parent, text="Sign Off",
                              command=lambda h=hour: self._sign_off_row(h),
                              font=font(9, bold=True), bg="#1a331a", fg=GREEN,
                              relief="flat", cursor="hand2", padx=6).grid(
                        row=grid_row, column=COL_SIGNOFF,
                        sticky="nsew", padx=2, pady=2)
                else:
                    tk.Label(parent, text="Add operators first",
                             font=font(9), fg=YELLOW, anchor="w", padx=4, **ckw).grid(
                        row=grid_row, column=COL_EMPLOYEE, columnspan=2,
                        sticky="nsew", padx=1, pady=1)
            else:
                tk.Label(parent, text="", **ckw).grid(
                    row=grid_row, column=COL_EMPLOYEE, sticky="nsew", padx=1, pady=1)
                tk.Label(parent, text="", **ckw).grid(
                    row=grid_row, column=COL_SIGNOFF,  sticky="nsew", padx=1, pady=1)

    # ── Sign-off / edit ───────────────────────────────────────────────────────
    def _sign_off_row(self, hour):
        op_var = self._row_op_var.get(hour)
        op     = op_var.get().strip() if op_var else ""
        if not op:
            messagebox.showwarning("Name Required", "Please select an operator.")
            return
        statuses = {k: v.get() for k, v in self._row_vars[hour].items()}
        save_signoff(self._view_date, hour, op, "", statuses)
        self._editing_hours.discard(hour)
        self.show_day_view(self._view_date)

    def _edit_row(self, hour):
        self._editing_hours.add(hour)
        self.show_day_view(self._view_date)

    def _copy_prev_row(self, hour, hour_idx):
        """Copy channel states from the closest previously signed row into this row."""
        prev = get_previous_row_statuses(self._view_date, hour_idx)
        if prev is None:
            return
        for chan_key, var in self._row_vars.get(hour, {}).items():
            var.set(prev.get(chan_key, 0))
        # ThreeStateCell traces on the vars will auto-refresh their display

    # ── Date navigation ───────────────────────────────────────────────────────
    def _prev_day(self):
        self._editing_hours.clear()
        self.show_day_view(self._view_date - datetime.timedelta(days=1))

    def _next_day(self):
        today    = broadcast_date(datetime.datetime.now())
        new_date = self._view_date + datetime.timedelta(days=1)
        if new_date <= today:
            self._editing_hours.clear()
            self.show_day_view(new_date)

    def _open_date_picker(self, _=None):
        with sqlite3.connect(DB_PATH) as c:
            dates = [r[0] for r in c.execute(
                "SELECT DISTINCT broadcast_date FROM signoffs ORDER BY broadcast_date DESC"
            ).fetchall()]
        today_str = str(broadcast_date(datetime.datetime.now()))
        if today_str not in dates:
            dates.insert(0, today_str)

        popup = tk.Toplevel(self)
        popup.title("Go to Date")
        popup.configure(bg=BG)
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  // 2 - 140
        y = self.winfo_y() + self.winfo_height() // 2 - 45
        popup.geometry(f"280x90+{x}+{y}")

        tk.Label(popup, text="Select date:", font=font(11), fg=TEXT, bg=BG).pack(pady=(10, 4))
        var = tk.StringVar(value=str(self._view_date))
        cmb = ttk.Combobox(popup, textvariable=var, values=dates, state="readonly", width=22)
        cmb.pack(pady=2)

        def go():
            sel = var.get()
            popup.destroy()
            if sel:
                self._editing_hours.clear()
                self.show_day_view(datetime.date.fromisoformat(sel))

        cmb.bind("<<ComboboxSelected>>", lambda _e: go())

    # ── Operators management (Ctrl+O) ─────────────────────────────────────────
    def show_operators(self):
        self._nav_select("ops")
        self._clear()

        wrapper = tk.Frame(self.content, bg=BG)
        wrapper.grid(row=0, column=0, sticky="nsew", padx=24, pady=16)
        wrapper.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        tk.Label(wrapper, text="Operators",
                 font=font(15, bold=True), fg=TEXT, bg=BG).pack(anchor="w", pady=(0, 4))
        tk.Label(wrapper,
                 text="Renaming an operator does not change their name on past sign-offs.",
                 font=font(11), fg=SUBTEXT, bg=BG).pack(anchor="w", pady=(0, 12))

        add_row = tk.Frame(wrapper, bg=BG_CARD, padx=14, pady=12)
        add_row.pack(fill="x")
        tk.Label(add_row, text="New operator name:", font=font(12),
                 fg=TEXT, bg=BG_CARD).pack(side="left", padx=(0, 8))
        self._new_op_entry = tk.Entry(add_row, font=font(12), width=28,
                                      bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat")
        self._new_op_entry.pack(side="left", padx=(0, 12), ipady=3)
        self._new_op_entry.focus_set()
        tk.Button(add_row, text="Add", command=self._add_operator,
                  font=font(12, bold=True), bg=BLUE, fg=BG,
                  relief="flat", padx=14, pady=4, cursor="hand2").pack(side="left")
        self._new_op_entry.bind("<Return>", lambda _e: self._add_operator())

        self._ops_list_frame = tk.Frame(wrapper, bg=BG)
        self._ops_list_frame.pack(fill="both", expand=True, pady=(12, 0))
        self._refresh_operators_list()

    def _refresh_operators_list(self):
        for w in self._ops_list_frame.winfo_children():
            w.destroy()
        operators = get_operators()
        if not operators:
            tk.Label(self._ops_list_frame, text="No operators added yet.",
                     font=font(12), fg=SUBTEXT, bg=BG).pack(pady=20)
            return
        for name in operators:
            row = tk.Frame(self._ops_list_frame, bg=BG_CARD, padx=14, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, font=font(12), fg=TEXT, bg=BG_CARD).pack(side="left")
            tk.Button(row, text="Remove",
                      command=lambda n=name: self._remove_operator(n),
                      font=font(10), bg=RED, fg=BG,
                      relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right")
            tk.Button(row, text="Rename",
                      command=lambda n=name: self._rename_operator_prompt(n),
                      font=font(10), bg=BG_CARD, fg=BLUE,
                      relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right", padx=6)

    def _add_operator(self):
        name = self._new_op_entry.get().strip()
        if not name:
            return
        if name in get_operators():
            messagebox.showwarning("Duplicate", f'"{name}" is already in the list.')
            return
        add_operator(name)
        self._new_op_entry.delete(0, tk.END)
        self._refresh_operators_list()

    def _remove_operator(self, name):
        if not messagebox.askyesno("Remove Operator",
                                   f'Remove "{name}" from the operator list?\n\n'
                                   f'Their name will remain on any existing sign-offs.'):
            return
        remove_operator(name)
        self._refresh_operators_list()

    def _rename_operator_prompt(self, old_name):
        popup = tk.Toplevel(self)
        popup.title("Rename Operator")
        popup.configure(bg=BG)
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width()  // 2 - 155
        y = self.winfo_y() + self.winfo_height() // 2 - 55
        popup.geometry(f"310x110+{x}+{y}")

        tk.Label(popup, text=f'Rename  "{old_name}"  to:',
                 font=font(11), fg=TEXT, bg=BG).pack(pady=(12, 4))
        var   = tk.StringVar(value=old_name)
        entry = tk.Entry(popup, textvariable=var, font=font(11), width=26,
                         bg=BG_CARD, fg=TEXT, insertbackground=TEXT, relief="flat")
        entry.pack(pady=2, ipady=3)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def do_rename():
            new_name = var.get().strip()
            if not new_name or new_name == old_name:
                popup.destroy()
                return
            existing = [op.lower() for op in get_operators() if op != old_name]
            if new_name.lower() in existing:
                messagebox.showwarning("Duplicate",
                                       f'"{new_name}" already exists.', parent=popup)
                return
            rename_operator(old_name, new_name)
            popup.destroy()
            self._refresh_operators_list()

        entry.bind("<Return>", lambda _: do_rename())
        tk.Button(popup, text="Rename", command=do_rename,
                  font=font(11, bold=True), bg=BLUE, fg=BG,
                  relief="flat", padx=14, pady=4, cursor="hand2").pack(pady=6)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
