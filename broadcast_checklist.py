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

# Columns that start a new station group (exclude the very first) — get extra left padding
GROUP_DIVIDER_COLS = {start for _, _, start in STATION_SPANS[1:]}

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
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                name   TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                active INTEGER NOT NULL DEFAULT 1
            );
        """)
        # Migration: add active column if it doesn't exist yet
        cols = [r[1] for r in c.execute("PRAGMA table_info(operators)").fetchall()]
        if "active" not in cols:
            c.execute("ALTER TABLE operators ADD COLUMN active INTEGER NOT NULL DEFAULT 1")


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
    """Return names of active operators only (for dropdowns)."""
    with sqlite3.connect(DB_PATH) as c:
        return [r[0] for r in c.execute(
            "SELECT name FROM operators WHERE active=1 ORDER BY name COLLATE NOCASE"
        ).fetchall()]


def get_all_operators():
    """Return [(name, active), ...] for all operators regardless of status."""
    with sqlite3.connect(DB_PATH) as c:
        return c.execute(
            "SELECT name, active FROM operators ORDER BY name COLLATE NOCASE"
        ).fetchall()


def add_operator(name):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT OR IGNORE INTO operators (name, active) VALUES (?, 1)", (name.strip(),))


def set_operator_active(name, active):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE operators SET active=? WHERE name=?", (1 if active else 0, name))


def rename_operator(old_name, new_name):
    """Rename an operator and update their name on all historical sign-offs."""
    new = new_name.strip()
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE operators SET name=? WHERE name=?", (new, old_name))
        c.execute("UPDATE signoffs SET operator_name=? WHERE operator_name=?", (new, old_name))


def get_previous_row_statuses(view_date, hour_idx):
    """Return (statuses, operator_name) from the closest signed row before hour_idx.
    Falls back to the previous broadcast day's last signed row if needed.
    Returns (None, None) if no previous row exists."""
    for i in range(hour_idx - 1, -1, -1):
        row = get_signoff(view_date, BCAST_HOURS[i])
        if row:
            return get_statuses(row[0]), row[1]
    prev = view_date - datetime.timedelta(days=1)
    for hour in reversed(BCAST_HOURS):
        row = get_signoff(prev, hour)
        if row:
            return get_statuses(row[0]), row[1]
    return None, None


# ── ThreeStateCell ─────────────────────────────────────────────────────────────
# States: 0 = Unknown (□), 1 = On Air (✔), 2 = Off Air (✘)
_CELL_CFG = {
    0: ("",   SUBTEXT,  None),        # Unknown — blank
    1: ("✔",  GREEN,    "#1a3328"),   # On Air
    2: ("✘",  RED,      "#331a1a"),   # Off Air
}


class ThreeStateCell(tk.Label):
    def __init__(self, parent, var, row_bg, readonly=False, warn_unknown=False, **kw):
        self._var          = var
        self._row_bg       = row_bg
        self._warn_unknown = warn_unknown
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
        if self._var.get() == 0 and self._warn_unknown:
            fg, bg = YELLOW, "#2e2800"   # yellow tint for unverified cells in signed rows
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
        self.title("OTA Checklist")
        self.geometry("1280x760")
        self.minsize(900, 520)
        self.configure(bg=BG)

        init_db()
        self._editing_hours = set()
        self._view_date     = None
        self._last_hour     = -1

        self._build_header()
        self.bind("<Control-o>", lambda _: self.show_operators())
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", lambda _: self.attributes("-fullscreen", False))

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self.content.columnconfigure(0, weight=1)

        self.show_day_view()
        self._tick()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HDR, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="OTA Checklist",
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

    def _clear(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.content.rowconfigure(0, weight=0)
        self.content.rowconfigure(1, weight=1)

    # ── Day view ──────────────────────────────────────────────────────────────
    def show_day_view(self, view_date=None):
        self._clear()
        self._scalable_widgets = []   # reset here so nav + grid widgets share one list

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

        left_btn = tk.Button(
            nav_bar, text="◀", command=self._prev_day,
            font=font(13), bg=BG_HDR, fg=TEXT, relief="flat",
            padx=14, pady=2, cursor="hand2", activebackground=BG_CARD,
        )
        left_btn.grid(row=0, column=0, padx=(14, 4))
        self._scalable_widgets.append((left_btn, False))

        date_lbl = tk.Label(
            nav_bar, text=view_date.strftime("%A, %B %d, %Y"),
            font=font(18, bold=True), fg=BLUE, bg=BG_HDR, cursor="hand2",
        )
        date_lbl.grid(row=0, column=1)
        date_lbl.bind("<Button-1>", self._open_date_picker)
        self._scalable_widgets.append((date_lbl, True))

        right_btn = tk.Button(
            nav_bar, text="▶", command=self._next_day,
            font=font(13),
            bg=BG_HDR, fg=(DIM if is_today else TEXT),
            relief="flat", padx=14, pady=2,
            cursor=("" if is_today else "hand2"),
            state=("disabled" if is_today else "normal"),
            activebackground=BG_CARD,
        )
        right_btn.grid(row=0, column=2, padx=(4, 14))
        self._scalable_widgets.append((right_btn, False))

        # Non-scrolling grid that expands to fill the window
        self.content.rowconfigure(1, weight=1)
        grid_frame = tk.Frame(self.content, bg=BG_BORDER)
        grid_frame.grid(row=1, column=0, sticky="nsew")

        self._build_grid(grid_frame, view_date, is_today, is_editable)

    def _build_grid(self, parent, view_date, is_today, is_editable):
        # Store context so individual rows can be rebuilt without a full redraw
        self._grid_parent  = parent
        self._is_today     = is_today
        self._is_editable  = is_editable
        self._operators    = get_operators()
        self._row_widgets  = {}   # {hour: [widgets]} for targeted rebuild
        self._row_vars     = {}
        self._row_op_var   = {}

        # Column weights — all columns share available width proportionally
        parent.columnconfigure(COL_TIME, weight=0, minsize=64)
        for c in range(COL_CHAN_START, COL_EMPLOYEE):
            parent.columnconfigure(c, weight=1, minsize=40)
        parent.columnconfigure(COL_EMPLOYEE, weight=2, minsize=86)
        parent.columnconfigure(COL_SIGNOFF,  weight=0, minsize=80)

        # Row weights — headers are compact; 24 data rows share all remaining height
        parent.rowconfigure(0, weight=0, minsize=20)
        parent.rowconfigure(1, weight=0, minsize=18)
        for i in range(2, 2 + len(BCAST_HOURS)):
            parent.rowconfigure(i, weight=1, minsize=20)

        hkw = dict(bg=BG_HDR, fg=TEXT, padx=2, pady=3, relief="flat")

        # Header row 0 — station group names
        tk.Label(parent, text="Time", font=font(18, bold=True), **hkw).grid(
            row=0, column=COL_TIME, sticky="nsew", padx=1, pady=1)
        for stn_id, span, start in STATION_SPANS:
            lpad = 6 if start in GROUP_DIVIDER_COLS else 1
            tk.Label(parent, text=stn_id, font=font(18, bold=True), **hkw).grid(
                row=0, column=start, columnspan=span, sticky="nsew", padx=(lpad, 1), pady=1)
        tk.Label(parent, text="Employee", font=font(18, bold=True), **hkw).grid(
            row=0, column=COL_EMPLOYEE, sticky="nsew", padx=(6, 1), pady=1)
        tk.Label(parent, text="", bg=BG_HDR).grid(
            row=0, column=COL_SIGNOFF, sticky="nsew", padx=1, pady=1)

        # Header row 1 — sub-channel names
        tk.Label(parent, text="", **hkw).grid(
            row=1, column=COL_TIME, sticky="nsew", padx=1, pady=1)
        for i, (_, short) in enumerate(CHANNEL_COLS):
            col_idx = COL_CHAN_START + i
            lpad = 6 if col_idx in GROUP_DIVIDER_COLS else 1
            tk.Label(parent, text=short, font=font(16), **hkw).grid(
                row=1, column=col_idx, sticky="nsew", padx=(lpad, 1), pady=1)
        tk.Label(parent, text="", **hkw).grid(
            row=1, column=COL_EMPLOYEE, sticky="nsew", padx=(6, 1), pady=1)
        tk.Label(parent, text="", bg=BG_HDR).grid(
            row=1, column=COL_SIGNOFF, sticky="nsew", padx=1, pady=1)

        for row_idx, hour in enumerate(BCAST_HOURS):
            self._build_row(hour, row_idx)

        parent.bind("<Configure>", self._on_grid_configure)

    def _build_row(self, hour, row_idx):
        """Build (or rebuild) a single data row. Appends new widgets to _scalable_widgets."""
        parent       = self._grid_parent
        view_date    = self._view_date
        is_today     = self._is_today
        is_editable  = self._is_editable
        operators    = self._operators
        now_hour     = datetime.datetime.now().hour

        grid_row         = row_idx + 2
        is_current       = is_today and (hour == now_hour)
        row_bg           = BG_CUR if is_current else (BG_ROW_A if row_idx % 2 == 0 else BG_ROW_B)
        edit_mode        = hour in self._editing_hours
        existing         = get_signoff(view_date, hour)
        effective_signed = (existing is not None) and not edit_mode
        prior            = get_statuses(existing[0]) if existing else {}
        readonly_cell    = effective_signed or not is_editable

        ckw   = dict(bg=row_bg, relief="flat")
        wlist = []   # widgets belonging to this row (for targeted teardown)

        # Time label
        hour_str = datetime.time(hour, 0).strftime("%I:%M %p").lstrip("0")
        time_lbl = tk.Label(parent, text=hour_str, font=font(9, bold=is_current),
                            fg=(BLUE if is_current else TEXT),
                            anchor="center", padx=4, **ckw)
        time_lbl.grid(row=grid_row, column=COL_TIME, sticky="nsew", padx=1, pady=1)
        wlist.append(time_lbl)
        self._scalable_widgets.append((time_lbl, is_current))
        if is_editable and not effective_signed:
            time_lbl.config(cursor="hand2")
            time_lbl.bind("<Button-1>",
                          lambda _e, h=hour, idx=row_idx: self._copy_prev_row(h, idx))

        # Channel cells
        self._row_vars[hour] = {}
        for i, (chan_key, _) in enumerate(CHANNEL_COLS):
            col_idx = COL_CHAN_START + i
            lpad    = 6 if col_idx in GROUP_DIVIDER_COLS else 1
            var = tk.IntVar(value=prior.get(chan_key, 0))
            self._row_vars[hour][chan_key] = var
            cell = ThreeStateCell(parent, var, row_bg=row_bg,
                                  readonly=readonly_cell, warn_unknown=effective_signed)
            cell.grid(row=grid_row, column=col_idx,
                      sticky="nsew", padx=(lpad, 1), pady=1)
            wlist.append(cell)
            self._scalable_widgets.append((cell, True))

        # Employee + sign-off columns
        if effective_signed:
            op_lbl = tk.Label(parent, text=existing[1],
                              font=font(9), fg=GREEN, anchor="center", **ckw)
            op_lbl.grid(row=grid_row, column=COL_EMPLOYEE, sticky="nsew", padx=1, pady=1)
            wlist.append(op_lbl)
            self._scalable_widgets.append((op_lbl, False))
            if is_editable:
                edit_btn = tk.Button(parent, text="Edit",
                                     command=lambda h=hour: self._edit_row(h),
                                     font=font(9), bg="#263326", fg=GREEN,
                                     relief="flat", cursor="hand2", padx=6)
                edit_btn.grid(row=grid_row, column=COL_SIGNOFF,
                              sticky="nsew", padx=2, pady=2)
                wlist.append(edit_btn)
                self._scalable_widgets.append((edit_btn, False))
            else:
                w = tk.Label(parent, text="", **ckw)
                w.grid(row=grid_row, column=COL_SIGNOFF, sticky="nsew", padx=1, pady=1)
                wlist.append(w)

        elif is_editable:
            if operators:
                op_var = tk.StringVar(value="")
                if edit_mode and existing and existing[1] in operators:
                    op_var.set(existing[1])
                self._row_op_var[hour] = op_var
                cmb = ttk.Combobox(parent, textvariable=op_var, values=operators,
                                   state="readonly", font=font(9))
                cmb.grid(row=grid_row, column=COL_EMPLOYEE, sticky="ew", padx=2, pady=3)
                wlist.append(cmb)
                self._scalable_widgets.append((cmb, False))
                signoff_btn = tk.Button(parent, text="Sign Off",
                                        command=lambda h=hour: self._sign_off_row(h),
                                        font=font(9, bold=True), bg="#1a331a", fg=GREEN,
                                        relief="flat", cursor="hand2", padx=6)
                signoff_btn.grid(row=grid_row, column=COL_SIGNOFF,
                                 sticky="nsew", padx=2, pady=2)
                wlist.append(signoff_btn)
                self._scalable_widgets.append((signoff_btn, True))
            else:
                no_op_lbl = tk.Label(parent, text="Add operators first",
                                     font=font(9), fg=YELLOW, anchor="w", padx=4, **ckw)
                no_op_lbl.grid(row=grid_row, column=COL_EMPLOYEE, columnspan=2,
                               sticky="nsew", padx=1, pady=1)
                wlist.append(no_op_lbl)
                self._scalable_widgets.append((no_op_lbl, False))
        else:
            for col in (COL_EMPLOYEE, COL_SIGNOFF):
                w = tk.Label(parent, text="", **ckw)
                w.grid(row=grid_row, column=col, sticky="nsew", padx=1, pady=1)
                wlist.append(w)

        self._row_widgets[hour] = wlist

    def _rebuild_row(self, hour):
        """Destroy and rebuild a single row without touching the rest of the grid."""
        for w in self._row_widgets.pop(hour, []):
            try:
                w.destroy()
            except tk.TclError:
                pass
        row_idx = BCAST_HOURS.index(hour)
        self._build_row(hour, row_idx)
        # Apply current font size to the new widgets immediately
        self.after_idle(lambda: self._rescale_fonts(self._grid_parent.winfo_height()))

    def _on_grid_configure(self, event):
        """Debounced handler — schedules a font rescale 80 ms after the last resize."""
        if getattr(self, "_rescale_job", None):
            self.after_cancel(self._rescale_job)
        h = event.height
        self._rescale_job = self.after(80, lambda: self._rescale_fonts(h))

    def _rescale_fonts(self, grid_height):
        """Resize all scalable fonts to fit the current row height."""
        self._rescale_job = None
        data_h = max(1, grid_height - 42)          # subtract ~2 fixed header rows
        row_h  = data_h / len(BCAST_HOURS)
        size   = max(7, int(row_h * 0.45))
        # Update all tracked widgets
        for widget, bold in getattr(self, "_scalable_widgets", []):
            try:
                widget.config(font=font(size, bold))
            except tk.TclError:
                pass   # widget was destroyed between resize and callback
        # Update all Combobox dropdowns via style (covers the dropdown list font)
        try:
            ttk.Style().configure("TCombobox", font=("Segoe UI", size))
        except Exception:
            pass

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
        self._rebuild_row(hour)

    def _edit_row(self, hour):
        self._editing_hours.add(hour)
        self._rebuild_row(hour)

    def _copy_prev_row(self, hour, hour_idx):
        """Copy channel states and operator from the closest previously signed row."""
        prev_statuses, prev_operator = get_previous_row_statuses(self._view_date, hour_idx)
        if prev_statuses is None:
            return
        for chan_key, var in self._row_vars.get(hour, {}).items():
            var.set(prev_statuses.get(chan_key, 0))
        # Copy operator only if no employee has been selected yet
        if prev_operator:
            op_var = self._row_op_var.get(hour)
            if op_var is not None and op_var.get() == "":
                op_var.set(prev_operator)

    # ── Date navigation ───────────────────────────────────────────────────────
    def _toggle_fullscreen(self, _=None):
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))

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
        self._clear()

        wrapper = tk.Frame(self.content, bg=BG)
        wrapper.grid(row=0, column=0, sticky="nsew", padx=24, pady=16)
        wrapper.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        title_row = tk.Frame(wrapper, bg=BG)
        title_row.pack(fill="x", pady=(0, 4))
        tk.Label(title_row, text="Operators",
                 font=font(15, bold=True), fg=TEXT, bg=BG).pack(side="left")
        tk.Button(title_row, text="← Back to Checklist",
                  command=lambda: self.show_day_view(self._view_date),
                  font=font(10), bg=BG_CARD, fg=BLUE,
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(side="right")

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
        all_ops = get_all_operators()
        active   = [(n, a) for n, a in all_ops if a]
        inactive = [(n, a) for n, a in all_ops if not a]

        if not all_ops:
            tk.Label(self._ops_list_frame, text="No operators added yet.",
                     font=font(12), fg=SUBTEXT, bg=BG).pack(pady=20)
            return

        def make_section(label_text, entries, is_active):
            tk.Label(self._ops_list_frame, text=label_text,
                     font=font(11, bold=True), fg=SUBTEXT, bg=BG).pack(
                anchor="w", pady=(12, 4))
            if not entries:
                tk.Label(self._ops_list_frame, text="None",
                         font=font(11), fg=DIM, bg=BG).pack(anchor="w", padx=4, pady=2)
                return
            for name, _ in entries:
                row = tk.Frame(self._ops_list_frame, bg=BG_CARD, padx=14, pady=8)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=name, font=font(12), fg=TEXT, bg=BG_CARD).pack(side="left")
                if is_active:
                    tk.Button(row, text="Deactivate",
                              command=lambda n=name: self._deactivate_operator(n),
                              font=font(10), bg=RED, fg=BG,
                              relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right")
                    tk.Button(row, text="Rename",
                              command=lambda n=name: self._rename_operator_prompt(n),
                              font=font(10), bg=BG_CARD, fg=BLUE,
                              relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right", padx=6)
                else:
                    tk.Button(row, text="Reactivate",
                              command=lambda n=name: self._reactivate_operator(n),
                              font=font(10), bg=GREEN, fg=BG,
                              relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right")

        make_section("Active Operators", active, True)
        make_section("Inactive Operators", inactive, False)

    def _add_operator(self):
        name = self._new_op_entry.get().strip()
        if not name:
            return
        all_names = [n.lower() for n, _ in get_all_operators()]
        if name.lower() in all_names:
            # Could be inactive — offer to reactivate instead
            for n, active in get_all_operators():
                if n.lower() == name.lower():
                    if not active:
                        if messagebox.askyesno("Inactive Operator",
                                               f'"{n}" already exists but is inactive.\n'
                                               f'Reactivate them instead?'):
                            set_operator_active(n, True)
                            self._new_op_entry.delete(0, tk.END)
                            self._refresh_operators_list()
                    else:
                        messagebox.showwarning("Duplicate", f'"{n}" is already in the list.')
                    return
        add_operator(name)
        self._new_op_entry.delete(0, tk.END)
        self._refresh_operators_list()

    def _deactivate_operator(self, name):
        set_operator_active(name, False)
        self._refresh_operators_list()

    def _reactivate_operator(self, name):
        set_operator_active(name, True)
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
            existing = [n.lower() for n, _ in get_all_operators() if n != old_name]
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
