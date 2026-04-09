#!/usr/bin/env python3
"""
Broadcast Checklist
Hourly on-air status tracking for broadcast stations.
Broadcast day starts at 5:00 AM and runs through 4:59 AM.
Data is stored in broadcast_log.db (SQLite) in the same folder as this script.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import datetime
import os

# ── Station configuration ──────────────────────────────────────────────────────
STATIONS = [
    {"id": "WICS", "network": "ABC",    "substations": ["CHARGE!", "Comet TV", "ROAR"]},
    {"id": "WICD", "network": "ABC",    "substations": ["CHARGE!", "Comet TV", "ROAR"]},
    {"id": "WRSP", "network": "FOX",    "substations": ["True Crime Network", "Antenna TV"]},
    {"id": "WCCU", "network": "FOX",    "substations": ["True Crime Network", "Antenna TV"]},
    {"id": "WBUI", "network": "The CW", "substations": ["Dabl", "The Nest", "Rewind TV"]},
]

BROADCAST_START_HOUR = 5  # 5:00 AM

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "broadcast_log.db")

# ── Broadcast-order hour list (5am first, 4am last) ────────────────────────────
BCAST_HOURS = list(range(BROADCAST_START_HOUR, 24)) + list(range(0, BROADCAST_START_HOUR))
HOUR_LABELS = [datetime.time(h, 0).strftime("%I:%M %p").lstrip("0") for h in BCAST_HOURS]

# ── Colors (dark Catppuccin-inspired palette) ──────────────────────────────────
BG       = "#1e1e2e"
BG_CARD  = "#313244"
BG_HDR   = "#181825"
BLUE     = "#89b4fa"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
YELLOW   = "#f9e2af"
TEXT     = "#cdd6f4"
SUBTEXT  = "#a6adc8"


def font(size, bold=False):
    return ("Segoe UI", size, "bold" if bold else "normal")


# ── Database helpers ───────────────────────────────────────────────────────────
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
        """)


def broadcast_date(dt: datetime.datetime) -> datetime.date:
    """Return the broadcast date for a given datetime (day starts at 5 AM)."""
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
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            "SELECT channel_key, on_air FROM channel_status WHERE signoff_id=?",
            (signoff_id,)
        ).fetchall()
    return {r[0]: bool(r[1]) for r in rows}


def save_signoff(bdate, hour, operator, notes, statuses: dict):
    now = datetime.datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO signoffs (broadcast_date, hour, operator_name, notes, signed_off_at) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(broadcast_date, hour) DO UPDATE SET "
            "operator_name=excluded.operator_name, "
            "notes=excluded.notes, "
            "signed_off_at=excluded.signed_off_at",
            (str(bdate), hour, operator, notes, now),
        )
        sid = c.execute(
            "SELECT id FROM signoffs WHERE broadcast_date=? AND hour=?", (str(bdate), hour)
        ).fetchone()[0]
        c.execute("DELETE FROM channel_status WHERE signoff_id=?", (sid,))
        c.executemany(
            "INSERT INTO channel_status (signoff_id, channel_key, on_air) VALUES (?,?,?)",
            [(sid, k, int(v)) for k, v in statuses.items()],
        )


# ── Reusable scrollable frame ──────────────────────────────────────────────────
class ScrollFrame(tk.Frame):
    """A tk.Frame with a vertical scrollbar. Add children to .inner."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=kw.get("bg", BG))
        self.canvas = tk.Canvas(self, bg=kw.get("bg", BG), highlightthickness=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=kw.get("bg", BG))
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")

        # Bind mouse-wheel (Windows/macOS = MouseWheel, Linux = Button-4/5)
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
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")


# ── Station card helper ────────────────────────────────────────────────────────
def build_station_cards(parent, channel_vars, readonly=False, statuses=None):
    """Render one card per station into `parent`. Populates channel_vars."""
    statuses = statuses or {}
    for stn in STATIONS:
        card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=5, padx=2)

        # ── Main channel ──────────────────────────────────────────────────────
        mkey = f"{stn['id']}__main"
        mvar = tk.BooleanVar(value=statuses.get(mkey, True))
        channel_vars[mkey] = mvar

        mrow = tk.Frame(card, bg=BG_CARD)
        mrow.pack(fill="x")

        tk.Checkbutton(
            mrow, variable=mvar, bg=BG_CARD, activebackground=BG_CARD,
            selectcolor=BG, state="disabled" if readonly else "normal",
        ).pack(side="left")

        tk.Label(
            mrow, text=f"[{stn['id']}]  {stn['network']}",
            font=font(13, bold=True), fg=BLUE, bg=BG_CARD,
        ).pack(side="left", padx=4)

        if readonly:
            on = statuses.get(mkey, False)
            tk.Label(
                mrow, text="ON AIR" if on else "OFF AIR",
                font=font(11, bold=True), fg=GREEN if on else RED, bg=BG_CARD,
            ).pack(side="right", padx=6)

        # ── Substations ───────────────────────────────────────────────────────
        for sub in stn["substations"]:
            skey = f"{stn['id']}__{sub}"
            svar = tk.BooleanVar(value=statuses.get(skey, True))
            channel_vars[skey] = svar

            srow = tk.Frame(card, bg=BG_CARD)
            srow.pack(fill="x", padx=32)

            tk.Checkbutton(
                srow, variable=svar, bg=BG_CARD, activebackground=BG_CARD,
                selectcolor=BG, state="disabled" if readonly else "normal",
            ).pack(side="left")

            tk.Label(srow, text=sub, font=font(11), fg=TEXT, bg=BG_CARD).pack(side="left", padx=4)

            if readonly:
                on = statuses.get(skey, False)
                tk.Label(
                    srow, text="ON AIR" if on else "OFF AIR",
                    font=font(10, bold=True), fg=GREEN if on else RED, bg=BG_CARD,
                ).pack(side="right", padx=6)


# ── Main application ───────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Broadcast Checklist")
        self.geometry("880x720")
        self.minsize(720, 500)
        self.configure(bg=BG)

        init_db()
        self._build_header()
        self._build_nav()

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.show_checklist()
        self._tick()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HDR, pady=12)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Broadcast Checklist",
            font=font(18, bold=True), fg=TEXT, bg=BG_HDR,
        ).pack(side="left", padx=20)
        self._lbl_bdate = tk.Label(hdr, text="", font=font(11), fg=SUBTEXT, bg=BG_HDR)
        self._lbl_bdate.pack(side="right", padx=16)
        self._lbl_time = tk.Label(hdr, text="", font=font(14), fg=BLUE, bg=BG_HDR)
        self._lbl_time.pack(side="right", padx=4)

    def _tick(self):
        now = datetime.datetime.now()
        bd = broadcast_date(now)
        self._lbl_time.config(text=now.strftime("%I:%M %p"))
        self._lbl_bdate.config(text=f"Broadcast Date: {bd.strftime('%A, %B %d, %Y')}")
        self.after(10_000, self._tick)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _build_nav(self):
        nav = tk.Frame(self, bg=BG, pady=10)
        nav.pack(fill="x", padx=24)
        self._btn_check = tk.Button(
            nav, text="Current Hour", command=self.show_checklist,
            font=font(11, bold=True), bg=BLUE, fg=BG, relief="flat",
            padx=16, pady=6, cursor="hand2",
        )
        self._btn_check.pack(side="left", padx=(0, 8))
        self._btn_hist = tk.Button(
            nav, text="History", command=self.show_history,
            font=font(11), bg=BG_CARD, fg=TEXT, relief="flat",
            padx=16, pady=6, cursor="hand2",
        )
        self._btn_hist.pack(side="left")

    def _nav_select(self, which):
        if which == "check":
            self._btn_check.config(bg=BLUE, fg=BG, font=font(11, bold=True))
            self._btn_hist.config(bg=BG_CARD, fg=TEXT, font=font(11))
        else:
            self._btn_hist.config(bg=BLUE, fg=BG, font=font(11, bold=True))
            self._btn_check.config(bg=BG_CARD, fg=TEXT, font=font(11))

    def _clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    # ── Checklist view ────────────────────────────────────────────────────────
    def show_checklist(self, edit=False):
        self._nav_select("check")
        self._clear()

        now   = datetime.datetime.now()
        bdate = broadcast_date(now)
        hour  = now.hour
        hour_str = now.replace(minute=0).strftime("%I:00 %p").lstrip("0")

        tk.Label(
            self.content, text=f"Hour Check — {hour_str}",
            font=font(15, bold=True), fg=TEXT, bg=BG,
        ).pack(anchor="w", pady=(12, 6))

        existing  = get_signoff(bdate, hour)
        signed_in = existing is not None and not edit

        # ── Already signed off banner ─────────────────────────────────────────
        if signed_in:
            sid, op, notes, sat = existing
            sat_fmt = datetime.datetime.fromisoformat(sat).strftime("%I:%M %p")
            banner = tk.Frame(self.content, bg="#1b4332", padx=14, pady=8)
            banner.pack(fill="x", pady=(0, 10))
            tk.Label(
                banner, text=f"\u2713  Signed off by {op} at {sat_fmt}",
                font=font(12, bold=True), fg=GREEN, bg="#1b4332",
            ).pack(side="left")
            if notes:
                tk.Label(
                    banner, text=f"   Notes: {notes}",
                    font=font(11), fg=YELLOW, bg="#1b4332",
                ).pack(side="left")
            tk.Button(
                banner, text="Edit / Correct",
                command=lambda: self.show_checklist(edit=True),
                font=font(10), bg="#2d6a4f", fg=GREEN,
                relief="flat", padx=10, pady=3, cursor="hand2",
            ).pack(side="right")

        # ── Station list (scrollable) ─────────────────────────────────────────
        self._ch_vars: dict[str, tk.BooleanVar] = {}
        sf = ScrollFrame(self.content, bg=BG)
        sf.pack(fill="both", expand=True)

        prior_statuses = get_statuses(existing[0]) if existing else {}
        build_station_cards(sf.inner, self._ch_vars, readonly=signed_in, statuses=prior_statuses)

        # ── Sign-off bar ──────────────────────────────────────────────────────
        if not signed_in:
            self._build_signoff_bar(
                bdate, hour,
                prefill_op=existing[1] if existing else "",
                prefill_notes=existing[2] if existing else "",
            )

    def _build_signoff_bar(self, bdate, hour, prefill_op="", prefill_notes=""):
        bar = tk.Frame(self.content, bg=BG_CARD, padx=14, pady=12)
        bar.pack(fill="x", pady=(10, 0))

        lbl_w = dict(font=font(12), fg=TEXT, bg=BG_CARD)
        ent_w = dict(font=font(12), bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat")

        tk.Label(bar, text="Operator:", **lbl_w).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._ent_op = tk.Entry(bar, width=22, **ent_w)
        self._ent_op.insert(0, prefill_op)
        self._ent_op.grid(row=0, column=1, padx=(0, 18), ipady=3)

        tk.Label(bar, text="Notes (optional):", **lbl_w).grid(row=0, column=2, sticky="w", padx=(0, 6))
        self._ent_notes = tk.Entry(bar, width=32, **ent_w)
        self._ent_notes.insert(0, prefill_notes)
        self._ent_notes.grid(row=0, column=3, padx=(0, 18), ipady=3)

        tk.Button(
            bar, text="Sign Off",
            command=lambda: self._do_signoff(bdate, hour),
            font=font(12, bold=True), bg=GREEN, fg=BG,
            relief="flat", padx=16, pady=5, cursor="hand2",
        ).grid(row=0, column=4)

        self._ent_op.focus_set()
        self.bind("<Return>", lambda _e: self._do_signoff(bdate, hour))

    def _do_signoff(self, bdate, hour):
        self.unbind("<Return>")
        op    = self._ent_op.get().strip()
        notes = self._ent_notes.get().strip()
        if not op:
            messagebox.showwarning("Name Required", "Please enter the operator's name before signing off.")
            self.bind("<Return>", lambda _e: self._do_signoff(bdate, hour))
            return
        statuses = {k: v.get() for k, v in self._ch_vars.items()}
        save_signoff(bdate, hour, op, notes, statuses)
        hour_str = datetime.datetime.now().replace(hour=hour, minute=0).strftime("%I:00 %p").lstrip("0")
        messagebox.showinfo("Signed Off", f"Hour {hour_str} signed off by {op}.")
        self.show_checklist()

    # ── History view ──────────────────────────────────────────────────────────
    def show_history(self):
        self._nav_select("hist")
        self._clear()

        tk.Label(
            self.content, text="History",
            font=font(15, bold=True), fg=TEXT, bg=BG,
        ).pack(anchor="w", pady=(12, 8))

        with sqlite3.connect(DB_PATH) as c:
            dates = [r[0] for r in c.execute(
                "SELECT DISTINCT broadcast_date FROM signoffs ORDER BY broadcast_date DESC"
            ).fetchall()]

        if not dates:
            tk.Label(
                self.content, text="No sign-off history yet.",
                font=font(13), fg=SUBTEXT, bg=BG,
            ).pack(pady=40)
            return

        # ── Filter bar ────────────────────────────────────────────────────────
        fbar = tk.Frame(self.content, bg=BG)
        fbar.pack(fill="x", pady=(0, 10))

        tk.Label(fbar, text="Date:", font=font(11), fg=TEXT, bg=BG).pack(side="left")
        self._hist_date = tk.StringVar(value=dates[0])
        ttk.Combobox(
            fbar, textvariable=self._hist_date, values=dates,
            state="readonly", width=14,
        ).pack(side="left", padx=(4, 20))

        tk.Label(fbar, text="Hour:", font=font(11), fg=TEXT, bg=BG).pack(side="left")
        self._hist_hour_lbl = tk.StringVar(value=HOUR_LABELS[0])
        ttk.Combobox(
            fbar, textvariable=self._hist_hour_lbl, values=HOUR_LABELS,
            state="readonly", width=12,
        ).pack(side="left", padx=(4, 16))

        tk.Button(
            fbar, text="Load", command=self._load_history,
            font=font(11), bg=BLUE, fg=BG, relief="flat",
            padx=12, pady=4, cursor="hand2",
        ).pack(side="left")

        self._hist_body = tk.Frame(self.content, bg=BG)
        self._hist_body.pack(fill="both", expand=True)

        self._load_history()

    def _load_history(self):
        for w in self._hist_body.winfo_children():
            w.destroy()

        sel_date = self._hist_date.get()
        lbl      = self._hist_hour_lbl.get()
        hour     = BCAST_HOURS[HOUR_LABELS.index(lbl)]

        row = get_signoff(sel_date, hour)
        if not row:
            tk.Label(
                self._hist_body, text="No record found for this date and hour.",
                font=font(12), fg=SUBTEXT, bg=BG,
            ).pack(pady=20)
            return

        sid, op, notes, sat = row
        sat_fmt = datetime.datetime.fromisoformat(sat).strftime("%I:%M %p")

        info = tk.Frame(self._hist_body, bg=BG)
        info.pack(fill="x", pady=(0, 8))
        tk.Label(
            info, text=f"Signed off by  {op}  at {sat_fmt}",
            font=font(12, bold=True), fg=GREEN, bg=BG,
        ).pack(side="left")
        if notes:
            tk.Label(
                info, text=f"   \u2502   Notes: {notes}",
                font=font(11), fg=YELLOW, bg=BG,
            ).pack(side="left", padx=8)

        statuses = get_statuses(sid)

        sf = ScrollFrame(self._hist_body, bg=BG)
        sf.pack(fill="both", expand=True)
        build_station_cards(sf.inner, {}, readonly=True, statuses=statuses)


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
