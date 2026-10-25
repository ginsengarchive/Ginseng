#!/usr/bin/env python3
"""
Ginseng
=======
A gematria window app (tkinter, ships with Python) that calculates the value of words
and phrases in many English, Hebrew and Greek gematria ciphers, remembers
everything you type, and highlights when a new word shares a value with an
earlier one in the same cipher.

    python gematria.py                  open the window
    python gematria.py "hello world"    quick calculation in the terminal
    python gematria.py "love" "hate"    compare two phrases in the terminal
    python gematria.py --list           list all ciphers

Files:  gematria.py (this file) · history.py (saving/importing/exporting phrases) ·
        logo_data.py (the embedded logo).  Keep them in the same folder.
Your history is saved in ~/.gematria_calculator.json and your settings
(ciphers on/off, accent colour, light/dark mode) in ~/.gematria_settings.json
"""

import argparse
import json
import os
import re
import string
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

from history import DEFAULT_PATH, Store      # history.py: saving, importing and exporting phrases

# ==========================================================================
# CIPHERS
# ==========================================================================

LATIN = string.ascii_lowercase

# name -> (script, {letter: value}).  Dicts keep insertion order = display order.
CIPHERS: dict[str, tuple[str, dict[str, int]]] = {}


def _add(name: str, script: str, table: dict[str, int]) -> None:
    CIPHERS[name] = (script, table)


def _latin(fn) -> dict[str, int]:
    """Build a Latin table from fn(i) where i is 0 for A ... 25 for Z."""
    return {ch: fn(i) for i, ch in enumerate(LATIN)}


# ---- English -------------------------------------------------------------
_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41,
           43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97, 101]
_SEPTENARY = [1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1, 1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1]
_CHALDEAN = dict(zip(LATIN, [1, 2, 3, 4, 5, 8, 3, 5, 1, 1, 2, 3, 4,
                              5, 7, 8, 1, 2, 3, 4, 6, 6, 6, 5, 1, 7]))
_ALW_ORDER = "alwbmxcnydozepfqgrhsitjukv"
_KEYBOARD_ORDER = "qwertyuiopasdfghjklzxcvbnm"
_BACON_ALPHABET = "abcdefghiklmnopqrstuwxyz"  # I=J and U=V
# Latin cipher (Agrippa): A-I = 1-9, K-S = 10-90, T 100, U 200, X 300, Y 400, Z 500,
# and the letters missing from the classical Latin alphabet come last: J = 600, V = 700, W = 900.
_LATIN_AGRIPPA = [1, 2, 3, 4, 5, 6, 7, 8, 9, 600, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100,   # A ... T
                  200, 700, 900, 300, 400, 500]                                              # U V W X Y Z


def _jewish(i: int) -> int:           # A-I = 1-9, J-R = 10-90, S-Z = 100-800
    return (i + 1) if i < 9 else (i - 8) * 10 if i < 18 else (i - 17) * 100


_add("Ordinal", "latin", _latin(lambda i: i + 1))
_add("Reverse Ordinal", "latin", _latin(lambda i: 26 - i))
_add("Reduction", "latin", _latin(lambda i: i % 9 + 1))
_add("Reverse Reduction", "latin", _latin(lambda i: (25 - i) % 9 + 1))
_add("Jewish (English)", "latin", _latin(_jewish))
_add("Latin (Agrippa)", "latin", dict(zip(LATIN, _LATIN_AGRIPPA)))
_add("Sumerian (Ordinal x6)", "latin", _latin(lambda i: (i + 1) * 6))
_add("Reverse Sumerian (Rev. x6)", "latin", _latin(lambda i: (26 - i) * 6))
_add("Satanic (Ordinal +35)", "latin", _latin(lambda i: i + 36))
_add("Reverse Satanic (Rev. +35)", "latin", _latin(lambda i: 61 - i))
_add("Francis Bacon", "latin",
     _latin(lambda i: _BACON_ALPHABET.index({"j": "i", "v": "u"}.get(LATIN[i], LATIN[i])) + 1))
_add("Chaldean", "latin", _CHALDEAN)
_add("Septenary", "latin", _latin(lambda i: _SEPTENARY[i]))
_add("Keyboard (QWERTY)", "latin", {ch: i + 1 for i, ch in enumerate(_KEYBOARD_ORDER)})
_add("ALW Kabbalah", "latin", {ch: i + 1 for i, ch in enumerate(_ALW_ORDER)})
_add("Trigonal", "latin", _latin(lambda i: (i + 1) * (i + 2) // 2))
_add("Squares", "latin", _latin(lambda i: (i + 1) ** 2))
_add("Primes", "latin", _latin(lambda i: _PRIMES[i]))

# ---- Hebrew --------------------------------------------------------------
_HEB_ORDER = "אבגדהוזחטיכלמנסעפצקרשת"
_HEB_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80, 90,
               100, 200, 300, 400]
_HEB_FINALS = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
_HEB_FINAL_GADOL = {"ך": 500, "ם": 600, "ן": 700, "ף": 800, "ץ": 900}


def _hebrew(fn) -> dict[str, int]:
    """Build a Hebrew table from fn(position 1-22, standard value).
    Final letters share the value of their regular form."""
    table = {ch: fn(i + 1, _HEB_VALUES[i]) for i, ch in enumerate(_HEB_ORDER)}
    for fin, reg in _HEB_FINALS.items():
        table[fin] = table[reg]
    return table


_add("Hebrew Standard", "hebrew", _hebrew(lambda pos, v: v))
_add("Hebrew Gadol", "hebrew", {**_hebrew(lambda pos, v: v), **_HEB_FINAL_GADOL})
_add("Hebrew Ordinal", "hebrew", _hebrew(lambda pos, v: pos))
_add("Hebrew Katan", "hebrew", _hebrew(lambda pos, v: int(str(v)[0])))
_add("Hebrew Atbash", "hebrew", _hebrew(lambda pos, v: _HEB_VALUES[22 - pos]))
_add("Hebrew Kidmi", "hebrew", _hebrew(lambda pos, v: v * (v + 1) // 2))
_add("Hebrew Perati", "hebrew", _hebrew(lambda pos, v: v * v))

# ---- Greek ---------------------------------------------------------------
_GREEK_ORDER = "αβγδεζηθικλμνξοπρστυφχψω"
_GREEK_VALUES = [1, 2, 3, 4, 5, 7, 8, 9, 10, 20, 30, 40, 50, 60, 70, 80,
                 100, 200, 300, 400, 500, 600, 700, 800]
_greek_iso = dict(zip(_GREEK_ORDER, _GREEK_VALUES))
_greek_iso["ς"] = 200  # final sigma
_greek_ord = {ch: i + 1 for i, ch in enumerate(_GREEK_ORDER)}
_greek_ord["ς"] = _greek_ord["σ"]
_add("Greek Isopsephy", "greek", _greek_iso)
_add("Greek Ordinal", "greek", _greek_ord)

SCRIPT_LABELS = {"latin": "English / Latin", "hebrew": "Hebrew", "greek": "Greek"}

# ==========================================================================
# CALCULATION
# ==========================================================================

# Letters that don't decompose into base letter + accent on their own.
_EXTRA_FOLDING = {"đ": "d", "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "þ": "th"}


@lru_cache(maxsize=8192)
def normalize(text: str) -> str:
    """Lowercase and strip accents/vowel points so č->c, š->s, ž->z, đ->d, ά->α, etc."""
    t = text.lower()
    for k, v in _EXTRA_FOLDING.items():
        t = t.replace(k, v)
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def scripts_in(text: str) -> set[str]:
    found = set()
    for c in normalize(text):
        if "a" <= c <= "z":
            found.add("latin")
        elif "א" <= c <= "ת":
            found.add("hebrew")
        elif "α" <= c <= "ω":
            found.add("greek")
    return found


def applicable_ciphers(text: str) -> list[str]:
    scripts = scripts_in(text)
    return [name for name, (script, _) in CIPHERS.items() if script in scripts]


def breakdown(text: str, cipher: str) -> list[tuple[str, int]]:
    table = CIPHERS[cipher][1]
    return [(c, table[c]) for c in normalize(text) if c in table]


@lru_cache(maxsize=32768)
def all_totals(text: str) -> dict[str, int]:
    """Total value of text in every cipher (letters of other scripts count as 0)."""
    norm = normalize(text)
    return {name: sum(table.get(c, 0) for c in norm) for name, (_, table) in CIPHERS.items()}


def digital_root(n: int) -> int:
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def phrase_key(text: str) -> str:
    """Identity of a phrase: its letters only, so 'Hello!' and 'hello' are the same entry."""
    return "".join(c for c in normalize(text) if c.isalpha())


def find_matches(text: str, history: list[dict], ciphers: list[str]) -> dict[str, list[str]]:
    """For each cipher, the earlier phrases whose value equals this phrase's value."""
    mine = all_totals(text)
    me = phrase_key(text)
    out: dict[str, list[str]] = {name: [] for name in ciphers}
    for entry in history:
        if phrase_key(entry["text"]) == me:
            continue
        theirs = all_totals(entry["text"])
        for name in ciphers:
            if mine[name] and theirs[name] == mine[name]:
                out[name].append(entry["text"])
    return out


# ==========================================================================
# SETTINGS   (cipher on/off + accent colour; the history itself is in history.py)
# ==========================================================================

SETTINGS_FILE = Path(os.environ.get("GEMATRIA_SETTINGS", Path.home() / ".gematria_settings.json"))
DEFAULT_ACCENT = "#ffab00"                 # a brighter amber than the original "#f5b942"
OLD_DEFAULT_ACCENT = "#f5b942"


class Settings:
    def __init__(self, path: Path = SETTINGS_FILE, legacy: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.accent = DEFAULT_ACCENT
        self.mode = "grey"                      # "grey", "light" or "black"
        self.disabled: set[str] = set()
        self.maximized = False                  # was the window maximized when it was closed?
        self.size = (1280, 800)                 # its size when it was a normal window
        if not self.load():
            # First run of this version: keep the cipher choices the older single-file version saved.
            try:
                old = json.loads(Path(legacy).read_text(encoding="utf-8"))
                self.disabled = {n for n in old.get("disabled", []) if n in CIPHERS}
            except (OSError, ValueError, AttributeError):
                pass

    def load(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            accent = str(data.get("accent", ""))
            self.accent = accent if re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else DEFAULT_ACCENT
            if self.accent.lower() == OLD_DEFAULT_ACCENT:      # still on the old default: use the brighter one
                self.accent = DEFAULT_ACCENT
            self.disabled = {n for n in data.get("disabled", []) if n in CIPHERS}
            mode = {"dark": "grey", "auto": "grey"}.get(data.get("mode"), data.get("mode"))   # older versions
            self.mode = mode if mode in ("grey", "light", "black") else "grey"
            self.maximized = data.get("maximized") is True
            try:
                w, h = (int(v) for v in data.get("size", ()))
                if 600 <= w <= 10000 and 400 <= h <= 10000:
                    self.size = (w, h)
            except (TypeError, ValueError):
                pass
            return True
        except (OSError, ValueError, AttributeError):
            return False

    def save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"accent": self.accent, "mode": self.mode, "disabled": sorted(self.disabled),
                                        "maximized": self.maximized, "size": list(self.size)}, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass


# ==========================================================================
# WINDOW
# ==========================================================================

MAX_CONTENT_WIDTH = 1180

# Colour themes. The accent colour is chosen separately by the user.
THEMES = {
    "grey": dict(BG="#121418", PANEL="#1b1e25", TILE="#21252d", BORDER="#2e333d", TEXT="#e8eaed",
                 MUTED="#8d95a3", SELECT="#2f4a7a", HOVER="#2b303a", PRESSED="#363c48", SCROLL="#3a404c"),
    "light": dict(BG="#f3f4f7", PANEL="#ffffff", TILE="#e9ebf0", BORDER="#d0d4dc", TEXT="#1b1e25",
                  MUTED="#667085", SELECT="#cfe0ff", HOVER="#dde1e8", PRESSED="#cdd2db", SCROLL="#bcc2cc"),
    "black": dict(BG="#000000", PANEL="#0b0b0e", TILE="#141519", BORDER="#27282e", TEXT="#eceef1",
                  MUTED="#8a8f99", SELECT="#1f3a66", HOVER="#1d1e23", PRESSED="#2b2c32", SCROLL="#35363d"),
}
THEME_ROLES = ("BG", "PANEL", "TILE", "BORDER", "TEXT", "MUTED", "SELECT")   # colours found on widgets
BG = PANEL = TILE = BORDER = TEXT = MUTED = SELECT = HOVER = PRESSED = SCROLL = ""


def set_theme(name: str) -> None:
    """Make `name` the current theme (the GUI code reads these module-level colours)."""
    global BG, PANEL, TILE, BORDER, TEXT, MUTED, SELECT, HOVER, PRESSED, SCROLL
    t = THEMES[name]
    BG, PANEL, TILE, BORDER = t["BG"], t["PANEL"], t["TILE"], t["BORDER"]
    TEXT, MUTED, SELECT = t["TEXT"], t["MUTED"], t["SELECT"]
    HOVER, PRESSED, SCROLL = t["HOVER"], t["PRESSED"], t["SCROLL"]


set_theme("grey")


PALETTE = [
    ("Amber", "#ffab00"), ("Orange", "#ff8a3d"), ("Coral", "#ff6b6b"), ("Rose", "#ff5fa2"),
    ("Purple", "#b48cff"), ("Indigo", "#7c8cff"), ("Blue", "#4da3ff"), ("Sky", "#5ad0f5"),
    ("Teal", "#2dd4bf"), ("Green", "#5fd068"), ("Lime", "#b8e04a"), ("Silver", "#cfd3da"),
]

# Shorter names so the number tiles stay compact
TILE_NAMES = {
    "Sumerian (Ordinal x6)": "Sumerian ×6", "Satanic (Ordinal +35)": "Satanic +35",
    "Keyboard (QWERTY)": "Keyboard", "Jewish (English)": "Jewish", "Francis Bacon": "Bacon",
    "Reverse Reduction": "Rev. Reduction", "Reverse Ordinal": "Rev. Ordinal",
    "Latin (Agrippa)": "Latin", "Reverse Sumerian (Rev. x6)": "Rev. Sumerian",
    "Reverse Satanic (Rev. +35)": "Rev. Satanic",
}

WORD_HINT = "Type a word or phrase and press Enter."
NUMBER_HINT = "Type a number to see every phrase in your history that has that value."


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def mix(color: str, other: str, t: float) -> str:
    """Blend `color` towards `other` by fraction t (0 = color, 1 = other)."""
    a, b = _rgb(color), _rgb(other)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _luminance(color: str) -> float:
    def f(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_on(color: str) -> str:
    """Dark or white text, whichever is easier to read on `color`."""
    dark = "#15110a"
    l = _luminance(color)
    return dark if (l + 0.05) / (_luminance(dark) + 0.05) >= 1.05 / (l + 0.05) else "#ffffff"


def readable(color: str, background: str, minimum: float = 3.0) -> str:
    """`color`, adjusted just enough to be readable as text/borders on `background`.
    Only the lightness changes (and colourful colours stay saturated), so amber becomes a
    deep golden amber on white rather than a muddy brown."""
    import colorsys
    lb = _luminance(background)

    def contrast(c: str) -> float:
        lc = _luminance(c)
        return (max(lc, lb) + 0.05) / (min(lc, lb) + 0.05)

    if contrast(color) >= minimum:
        return color
    h, l, sat = colorsys.rgb_to_hls(*(v / 255 for v in _rgb(color)))
    if sat > 0.25:
        sat = max(sat, 0.9)
    step = -0.01 if lb > 0.5 else 0.01                  # darker on light backgrounds, lighter on dark ones
    for _ in range(100):
        l = min(max(l + step, 0.0), 1.0)
        c = "#%02x%02x%02x" % tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l, sat))
        if contrast(c) >= minimum:
            return c
    return "#000000" if lb > 0.5 else "#ffffff"


def run_gui() -> None:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import colorchooser, filedialog, ttk
    try:
        from logo_data import LOGO_ICON, LOGO_SMALL, LOGO_SMALL_LIGHT
    except ImportError:                       # the app still works without the logo file
        LOGO_ICON = LOGO_SMALL = LOGO_SMALL_LIGHT = ""

    class Flow(tk.Frame):
        """Lays out equal-sized children left to right and wraps to new rows
        (each row centred) when they don't fit the width."""

        def __init__(self, parent, gap: int = 8, **kw):
            super().__init__(parent, **kw)
            self.gap = gap
            self.items: list[tk.Widget] = []
            self.bind("<Configure>", lambda e: self.reflow(e.width))

        def set_items(self, items: list) -> None:
            for w in self.items:
                w.destroy()
            self.items = items
            self.reflow(self.winfo_width())

        def reflow(self, width: int) -> None:
            if not self.items:
                self.configure(height=1)
                return
            self.update_idletasks()
            tw = max(w.winfo_reqwidth() for w in self.items)
            th = max(w.winfo_reqheight() for w in self.items)
            width = max(width, tw)
            per_row = max(1, (width + self.gap) // (tw + self.gap))
            y = 0
            for start in range(0, len(self.items), per_row):
                row = self.items[start:start + per_row]
                x = max(0, (width - (len(row) * tw + (len(row) - 1) * self.gap)) // 2)
                for w in row:
                    w.place(x=x, y=y, width=tw, height=th)
                    x += tw + self.gap
                y += th + self.gap
            self.configure(height=y - self.gap)

    class ScrollPage(tk.Frame):
        """A page whose content is centred (max width) and scrolls vertically."""

        def __init__(self, parent):
            super().__init__(parent, bg=BG)
            self.region_h = 1
            self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, yscrollincrement=24)
            vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
            self.canvas.pack(side="left", fill="both", expand=True)
            self.content = tk.Frame(self.canvas, bg=BG)
            self.window = self.canvas.create_window(0, 0, window=self.content, anchor="n")
            self.canvas.bind("<Configure>", self._on_canvas_configure)
            self.content.bind("<Configure>", lambda e: self._update_region())

        def _on_canvas_configure(self, event) -> None:
            self.canvas.itemconfigure(self.window, width=min(event.width - 32, MAX_CONTENT_WIDTH))
            self.canvas.coords(self.window, event.width // 2, 0)
            self._update_region()

        def _update_region(self) -> None:
            self.region_h = max(self.content.winfo_reqheight(), self.canvas.winfo_height())
            self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.region_h))

        def scroll(self, step: int) -> None:
            self.canvas.yview_scroll(step * 3, "units")

        def to_top(self) -> None:
            self.canvas.yview_moveto(0)

        def scroll_to(self, widget) -> None:
            self.update_idletasks()
            y = widget.winfo_rooty() - self.content.winfo_rooty()
            self.canvas.yview_moveto(max(0.0, (y - 12) / max(self.region_h, 1)))

    class App(tk.Tk):
        def __init__(self, store: Store, settings: Settings):
            super().__init__()
            self.store, self.settings = store, settings
            self.theme_name = settings.mode
            set_theme(self.theme_name)
            self.accent = settings.accent
            self.accent_fg = readable(self.accent, PANEL)      # accent as text/border colour
            self.configure(bg=BG)
            self.title("Ginseng")
            self.geometry("%dx%d" % settings.size)
            self.minsize(980, 520)
            if settings.maximized:
                self._set_zoomed(True)
            self.protocol("WM_DELETE_WINDOW", self._on_close)

            family = tkfont.nametofont("TkDefaultFont").actual("family")
            self.f_entry = (family, 20)
            self.f_tile_name = (family, 9)
            self.f_tile_value = (family, 17, "bold")
            self.f_head = (family, 12, "bold")
            self.f_word = (family, 12)
            self.f_small = (family, 10)
            self.f_tab = (family, 11, "bold")

            self.cipher_vars = {n: tk.BooleanVar(value=n not in settings.disabled) for n in CIPHERS}
            self.filter_var = tk.StringVar()
            self.filter_var.trace_add("write", lambda *a: self.refresh_history())
            self.active = "word"
            self.current_text = ""
            self.current_matches: dict[str, list[str]] = {}
            self.number_query: int | None = None
            self.word_groups: dict[str, tk.Widget] = {}
            self.number_groups: dict[str, tk.Widget] = {}
            self.shown_history: list[dict] = []
            self.accent_entries: list[tk.Entry] = []
            self.cipher_win = self.color_win = None
            self.swatches: dict[str, tk.Widget] = {}
            self.mode_canvases: dict[str, tk.Canvas] = {}
            self.clear_state = "idle"              # idle -> cooling (greyed out, 5 s) -> ready (can confirm)
            self._clear_job = None
            self._flash_job = None
            self._detail_job = None
            self.logo_label = None
            self.logo_imgs: dict[str, tk.PhotoImage] = {}

            self._style()
            self._build()
            self.update_idletasks()
            self._dark_titlebar(self, self.theme_name != "light")
            self.bind_all("<MouseWheel>", self._on_wheel)
            self.bind_all("<Button-4>", self._on_wheel)
            self.bind_all("<Button-5>", self._on_wheel)
            self.show_tab("word")
            self.refresh_history()

        # ================= look =============================================
        def _style(self) -> None:
            a = self.accent
            on = text_on(a)
            s = ttk.Style(self)
            s.theme_use("clam")
            s.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL, bordercolor=BORDER,
                        lightcolor=BG, darkcolor=BG, troughcolor=BG, focuscolor=BG)
            s.configure("TButton", background=TILE, foreground=TEXT, bordercolor=BORDER,
                        padding=(14, 7), relief="flat")
            s.map("TButton", background=[("disabled", TILE), ("pressed", PRESSED), ("active", HOVER)],
                  foreground=[("disabled", mix(MUTED, BG, 0.45))])
            s.configure("Bar.TButton", padding=(11, 6))
            s.configure("Danger.TButton", background="#c0392b", foreground="#ffffff", bordercolor="#c0392b")
            s.map("Danger.TButton", background=[("pressed", "#a93226"), ("active", "#d9473a")],
                  foreground=[("pressed", "#ffffff"), ("active", "#ffffff")])
            s.configure("Accent.TButton", background=a, foreground=on, bordercolor=a)
            s.map("Accent.TButton", background=[("pressed", mix(a, "#000000", 0.2)),
                                                ("active", mix(a, "#ffffff", 0.2))],
                  foreground=[("pressed", on), ("active", on)])
            s.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorcolor=PANEL,
                        indicatorbackground=PANEL, indicatorforeground=on,
                        upperbordercolor=MUTED, lowerbordercolor=MUTED)
            s.map("TCheckbutton", background=[("active", BG)],
                  indicatorcolor=[("selected", a), ("pressed", a)],
                  indicatorbackground=[("selected", a), ("pressed", a)],
                  indicatorforeground=[("selected", on), ("!selected", PANEL)])
            s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        borderwidth=0, rowheight=28)
            s.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
            s.configure("Treeview.Heading", background=TILE, foreground=TEXT, relief="flat", padding=6)
            s.map("Treeview.Heading", background=[("active", HOVER)])
            s.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            s.configure("Vertical.TScrollbar", background=SCROLL, troughcolor=BG, bordercolor=BG,
                        lightcolor=SCROLL, darkcolor=SCROLL, relief="flat", borderwidth=0, gripsize=0, width=10)
            s.map("Vertical.TScrollbar", background=[("active", MUTED), ("pressed", MUTED)],
                  lightcolor=[("active", MUTED), ("pressed", MUTED)], darkcolor=[("active", MUTED), ("pressed", MUTED)])

        def _set_zoomed(self, on: bool) -> None:
            try:
                self.state("zoomed" if on else "normal")          # Windows / macOS
            except tk.TclError:
                try:
                    self.attributes("-zoomed", on)                # Linux
                except tk.TclError:
                    pass

        def _is_zoomed(self) -> bool:
            try:
                return self.state() == "zoomed" or bool(self.attributes("-zoomed"))
            except tk.TclError:
                return False

        def _on_close(self) -> None:
            """Remember maximized-or-windowed (and the window size) for the next start."""
            self.settings.maximized = self._is_zoomed()
            if not self.settings.maximized and self.winfo_width() > 1:
                self.settings.size = (self.winfo_width(), self.winfo_height())
            self.settings.save()
            self.destroy()

        @staticmethod
        def _dark_titlebar(win, dark: bool = True) -> None:
            """Dark or light title bar on Windows 10/11 (harmless no-op elsewhere)."""
            if sys.platform != "win32":
                return
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
                for attr in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(1 if dark else 0)), 4)
            except Exception:
                pass

        def _entry(self, parent, var, font, **kw) -> "tk.Entry":
            e = tk.Entry(parent, textvariable=var, font=font, bg=PANEL, fg=TEXT, insertbackground=self.accent_fg,
                         selectbackground=SELECT, selectforeground=TEXT, relief="flat", bd=0,
                         highlightthickness=2, highlightbackground=BORDER, highlightcolor=self.accent_fg, **kw)
            self.accent_entries.append(e)
            return e

        # ================= window skeleton ===================================
        def _build(self) -> None:
            bar = tk.Frame(self, bg=BG)
            bar.pack(fill="x", padx=14, pady=(8, 0))

            # logo (click = back to the default view)
            if LOGO_SMALL:
                self.logo_imgs = {"dark": tk.PhotoImage(data=LOGO_SMALL),
                                  "light": tk.PhotoImage(data=LOGO_SMALL_LIGHT or LOGO_SMALL)}
                logo = tk.Label(bar, image=self.logo_imgs["light" if self.theme_name == "light" else "dark"],
                                bg=BG, cursor="hand2")
                self.logo_label = logo
                try:
                    self.icon_img = tk.PhotoImage(data=LOGO_ICON)
                    self.iconphoto(True, self.icon_img)
                except tk.TclError:
                    pass
            else:
                logo = tk.Label(bar, text="GINSENG", bg=BG, fg=MUTED, font=self.f_tab, cursor="hand2")
            logo.pack(side="left", padx=(0, 18))
            logo.bind("<Button-1>", lambda e: self.reset())

            # tabs
            self.tab_widgets: dict[str, tuple] = {}
            for key, text in (("word", "Word Search"), ("number", "Number Search"), ("history", "History")):
                cell = tk.Frame(bar, bg=BG, cursor="hand2")
                label = tk.Label(cell, text=text, bg=BG, font=self.f_tab, padx=14, pady=8)
                under = tk.Frame(cell, height=3, bg=BG)
                label.pack()
                under.pack(fill="x")
                cell.pack(side="left")
                for w in (cell, label, under):
                    w.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
                self.tab_widgets[key] = (label, under)

            # action buttons (packed right-to-left)
            for text, command in reversed([("Copy results", self.copy_results),
                                           ("Import history", self.import_history),
                                           ("Export history", self.export_history),
                                           ("Ciphers", self.open_ciphers),
                                           ("Colors", self.open_colors)]):
                ttk.Button(bar, text=text, style="Bar.TButton", command=command).pack(side="right", padx=(6, 0))
            tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))

            # footer: messages on the left, history size on the right
            foot = tk.Frame(self, bg=PANEL)
            foot.pack(side="bottom", fill="x")
            self.note_var, self.count_var = tk.StringVar(), tk.StringVar()
            tk.Label(foot, textvariable=self.note_var, bg=PANEL, fg=self.accent_fg, font=self.f_small,
                     anchor="w").pack(side="left", padx=14, pady=5)
            tk.Label(foot, textvariable=self.count_var, bg=PANEL, fg=MUTED,
                     font=self.f_small).pack(side="right", padx=14)
            self.note_label = foot.winfo_children()[0]

            # pages
            pages = tk.Frame(self, bg=BG)
            pages.pack(fill="both", expand=True)
            self.word_page = ScrollPage(pages)
            self.number_page = ScrollPage(pages)
            self.history_page = tk.Frame(pages, bg=BG)
            self.page_for = {"word": self.word_page, "number": self.number_page, "history": self.history_page}
            self._build_word_tab(self.word_page.content)
            self._build_number_tab(self.number_page.content)
            self._build_history_tab(self.history_page)

        def show_tab(self, key: str) -> None:
            for k, page in self.page_for.items():
                if k != key:
                    page.pack_forget()
            self.page_for[key].pack(fill="both", expand=True)
            self.active = key
            if key != "history":
                self._disarm()
            self._paint_tabs()
            if key == "word":
                self.entry.focus_set()
            elif key == "number":
                if self.number_query is not None:        # history may have changed meanwhile
                    self._run_number(self.number_query, reset_scroll=False)
                self.number_entry.focus_set()
            else:
                self.refresh_history()
                self.filter_entry.focus_set()

        def _paint_tabs(self) -> None:
            for key, (label, under) in self.tab_widgets.items():
                on = key == self.active
                label.configure(fg=TEXT if on else MUTED)
                under.configure(bg=self.accent if on else BG)

        def reset(self) -> None:
            """Back to the default view: empty inputs and results, Word Search tab, top of page."""
            for var in (self.entry_var, self.number_var, self.filter_var):
                var.set("")
            self.current_text, self.current_matches, self.number_query = "", {}, None
            self._clear_detail()
            self._disarm()
            self.status.set(WORD_HINT)
            self.number_status.set(NUMBER_HINT)
            for flow, box in ((self.flow, self.matches), (self.nflow, self.number_matches)):
                flow.set_items([])
                for w in box.winfo_children():
                    w.destroy()
            self.word_groups, self.number_groups = {}, {}
            self.show_tab("word")
            self.word_page.to_top()
            self.number_page.to_top()

        def flash(self, message: str, ms: int = 8000) -> None:
            self.note_var.set(message)
            if self._flash_job:
                self.after_cancel(self._flash_job)
            self._flash_job = self.after(ms, lambda: self.note_var.set(""))

        def _on_wheel(self, event) -> None:
            page = self.page_for.get(self.active)
            if not isinstance(page, ScrollPage):
                return
            try:
                if event.widget.winfo_toplevel() is not self:
                    return
            except (KeyError, tk.TclError, AttributeError):
                return
            if getattr(event, "num", 0) == 4:
                step = -1
            elif getattr(event, "num", 0) == 5:
                step = 1
            else:
                step = -1 if event.delta > 0 else 1
            page.scroll(step)

        # ================= shared building blocks ============================
        def _tile(self, parent, name: str, big: str, small: str, highlight: bool, command, hover=None):
            edge = self.accent_fg if highlight else BORDER
            tile = tk.Frame(parent, bg=TILE, highlightthickness=1, highlightbackground=edge,
                            highlightcolor=edge, cursor="hand2")
            labels = [
                tk.Label(tile, text=TILE_NAMES.get(name, name), bg=TILE, fg=MUTED, font=self.f_tile_name),
                tk.Label(tile, text=big, bg=TILE, fg=self.accent_fg if highlight else TEXT, font=self.f_tile_value),
                tk.Label(tile, text=small or " ", bg=TILE, fg=self.accent_fg, font=(self.f_tile_name[0], 8)),
            ]
            labels[0].pack(padx=12, pady=(8, 0))
            labels[1].pack(padx=12)
            labels[2].pack(padx=12, pady=(0, 7))
            for w in (tile, *labels):
                w.bind("<Button-1>", lambda e, n=name: command(n))
                if hover:                      # hovering shows the calculation under the tiles
                    w.bind("<Enter>", lambda e, n=name: self._show_detail(*hover(n)))
                    w.bind("<Leave>", lambda e: self._hide_detail_soon())
            return tile

        def _cards(self, container, names: list[str], words_map: dict, values: dict, noun: str) -> dict:
            """One card per cipher: 'Ordinal = 54   8 words' followed by the words, one per row."""
            groups = {}
            for name in names:
                words = words_map[name]
                card = tk.Frame(container, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
                card.pack(fill="x", pady=6)
                head = tk.Frame(card, bg=PANEL)
                head.pack(fill="x", padx=16, pady=(12, 6))
                tk.Label(head, text=name, bg=PANEL, fg=TEXT, font=self.f_head).pack(side="left")
                tk.Label(head, text=f"  =  {values[name]}", bg=PANEL, fg=self.accent_fg,
                         font=self.f_head).pack(side="left")
                tk.Label(head, text=f"   {len(words)} {noun}{'s' if len(words) != 1 else ''}",
                         bg=PANEL, fg=MUTED, font=self.f_small).pack(side="left")
                for word in words:
                    tk.Label(card, text=word, bg=PANEL, fg=TEXT, font=self.f_word, anchor="w",
                             justify="left", wraplength=1050).pack(fill="x", padx=(28, 16), pady=1)
                tk.Frame(card, bg=PANEL, height=10).pack()
                groups[name] = card
            return groups

        def _empty_card(self, container, message: str) -> None:
            card = tk.Frame(container, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
            card.pack(fill="x", pady=6)
            tk.Label(card, text=message, bg=PANEL, fg=MUTED, font=self.f_word, pady=22).pack()

        @staticmethod
        def _clear(box) -> None:
            for w in box.winfo_children():
                w.destroy()

        def enabled_names(self, text: str) -> list[str]:
            return [n for n in applicable_ciphers(text) if self.cipher_vars[n].get()]

        def _refresh_views(self) -> None:
            """Redraw results after a change in ciphers, colours or history."""
            if self.current_text:
                self.calculate(text=self.current_text, add=False, reset_scroll=False)
            if self.number_query is not None:
                self._run_number(self.number_query, reset_scroll=False)

        # ================= tab 1: word search ================================
        def _build_word_tab(self, page) -> None:
            row = tk.Frame(page, bg=BG)
            row.pack(pady=(30, 6))
            self.entry_var = tk.StringVar()
            self.entry = self._entry(row, self.entry_var, self.f_entry, width=30, justify="center")
            self.entry.pack(side="left", ipady=11)
            self.entry.bind("<Return>", lambda e: self.calculate())
            ttk.Button(row, text="Calculate", style="Accent.TButton",
                       command=self.calculate).pack(side="left", padx=(10, 0), ipady=4)

            self.status = tk.StringVar(value=WORD_HINT)
            tk.Label(page, textvariable=self.status, bg=BG, fg=MUTED, font=self.f_small,
                     wraplength=900, justify="center").pack(pady=(4, 18))
            self.flow = Flow(page, gap=8, bg=BG)
            self.flow.pack(fill="x")
            # the calculation for whichever result the mouse is over (two lines are always reserved)
            self.detail = tk.StringVar()
            tk.Label(page, textvariable=self.detail, bg=BG, fg=TEXT, font=self.f_word, wraplength=1000,
                     justify="center", height=2).pack(pady=(12, 0))
            self.matches = tk.Frame(page, bg=BG)
            self.matches.pack(fill="x", pady=(14, 40))

        def calculate(self, text: str | None = None, add: bool = True, reset_scroll: bool = True) -> None:
            text = " ".join((text if text is not None else self.entry_var.get()).split())
            if not text:
                return
            self.current_text = text
            names = self.enabled_names(text)
            self._clear_detail()
            self._clear(self.matches)
            self.word_groups = {}
            if not names:
                self.current_matches = {}
                self.flow.set_items([])
                self.status.set("No usable letters for the ciphers that are switched on "
                                "(English, Hebrew and Greek letters are supported).")
                return

            self.current_matches = find_matches(text, self.store.history, names)
            totals = all_totals(text)
            with_matches = [n for n in names if self.current_matches[n]]
            self.flow.set_items([
                self._tile(self.flow, n, str(totals[n]),
                           (f"{len(self.current_matches[n])} match"
                            f"{'es' if len(self.current_matches[n]) != 1 else ''}") if self.current_matches[n] else "",
                           bool(self.current_matches[n]), self.on_word_tile, self.tip_text) for n in names])

            if with_matches:
                tk.Label(self.matches, text="SAME VALUE IN YOUR HISTORY", bg=BG, fg=MUTED,
                         font=(self.f_small[0], 10, "bold")).pack(anchor="w", pady=(0, 4))
                self.word_groups = self._cards(self.matches, with_matches, self.current_matches, totals, "word")
                self.status.set(f"“{text}” shares a value with your history in "
                                f"{len(with_matches)} cipher{'s' if len(with_matches) != 1 else ''}  ·  highlighted below")
            else:
                self._empty_card(self.matches, "No earlier phrase has the same value yet.\n"
                                               "Keep adding words — matches will appear here.")
                self.status.set(f"“{text}”  ·  no matches in your history yet")
            if add and self.store.add(text):
                self.refresh_history()
            if reset_scroll:
                self.word_page.to_top()

        def tip_text(self, name: str) -> tuple[str, str]:
            """Title and calculation shown while hovering over a cipher's result."""
            parts = " + ".join(f"{c}={v}" for c, v in breakdown(self.current_text, name))
            if len(parts) > 600:
                parts = parts[:600] + " …"
            return name, f"{parts}  =  {all_totals(self.current_text)[name]}"

        def _show_detail(self, title: str, body: str) -> None:
            self._cancel_detail_job()
            self.detail.set(f"{title}:   {body}")

        def _hide_detail_soon(self) -> None:
            self._cancel_detail_job()
            self._detail_job = self.after(150, lambda: self.detail.set(""))

        def _clear_detail(self) -> None:
            self._cancel_detail_job()
            self.detail.set("")

        def _cancel_detail_job(self) -> None:
            if self._detail_job:
                try:
                    self.after_cancel(self._detail_job)
                except tk.TclError:
                    pass
                self._detail_job = None

        def on_word_tile(self, name: str) -> None:
            """Clicking a result jumps to the list of words that share its value."""
            if name in self.word_groups:
                self.word_page.scroll_to(self.word_groups[name])

        # ================= tab 2: number search ==============================
        def _build_number_tab(self, page) -> None:
            row = tk.Frame(page, bg=BG)
            row.pack(pady=(30, 6))
            self.number_var = tk.StringVar()
            self.number_entry = self._entry(row, self.number_var, self.f_entry, width=16, justify="center")
            self.number_entry.pack(side="left", ipady=11)
            self.number_entry.bind("<Return>", lambda e: self.search_number())
            ttk.Button(row, text="Search", style="Accent.TButton",
                       command=self.search_number).pack(side="left", padx=(10, 0), ipady=4)
            self.number_status = tk.StringVar(value=NUMBER_HINT)
            tk.Label(page, textvariable=self.number_status, bg=BG, fg=MUTED, font=self.f_small,
                     wraplength=900, justify="center").pack(pady=(4, 18))
            self.nflow = Flow(page, gap=8, bg=BG)
            self.nflow.pack(fill="x")
            self.number_matches = tk.Frame(page, bg=BG)
            self.number_matches.pack(fill="x", pady=(24, 40))

        def search_number(self) -> None:
            raw = self.number_var.get().strip().replace(",", "").replace(" ", "")
            if not raw.isdigit():
                self.number_status.set("Please type a number, for example 54.")
                return
            self._run_number(int(raw), reset_scroll=True)

        def _run_number(self, n: int, reset_scroll: bool = True) -> None:
            self.number_query = n
            self._clear(self.number_matches)
            self.number_groups = {}
            names = [c for c, v in self.cipher_vars.items() if v.get()]
            hits: dict[str, list[str]] = {c: [] for c in names}
            if n > 0:
                for entry in reversed(self.store.history):          # newest first
                    totals = all_totals(entry["text"])
                    for c in names:
                        if totals[c] == n:
                            hits[c].append(entry["text"])
            hits = {c: w for c, w in hits.items() if w}
            if not hits:
                self.nflow.set_items([])
                self._empty_card(self.number_matches,
                                 f"No phrase in your history has the value {n} in the ciphers that are on."
                                 if self.store.history else
                                 "Your history is empty. Look up some words in Word Search first.")
                self.number_status.set(f"{n}  ·  no matches")
            else:
                unique = len({w for words in hits.values() for w in words})
                self.nflow.set_items([self._tile(self.nflow, c, str(len(w)), "phrases", True, self.on_number_tile)
                                      for c, w in hits.items()])
                self.number_groups = self._cards(self.number_matches, list(hits), hits,
                                                 {c: n for c in hits}, "phrase")
                self.number_status.set(f"{n}  ·  {unique} phrase{'s' if unique != 1 else ''} in your history, "
                                       f"across {len(hits)} cipher{'s' if len(hits) != 1 else ''}")
            self.number_hits = hits
            if reset_scroll:
                self.number_page.to_top()

        def on_number_tile(self, name: str) -> None:
            if name in self.number_groups:
                self.number_page.scroll_to(self.number_groups[name])

        # ================= tab 3: history ====================================
        def _build_history_tab(self, page) -> None:
            wrap = tk.Frame(page, bg=BG)
            wrap.pack(fill="both", expand=True, padx=40, pady=(24, 18))
            top = tk.Frame(wrap, bg=BG)
            top.pack(fill="x")
            tk.Label(top, text="Filter", bg=BG, fg=MUTED, font=self.f_small).pack(side="left", padx=(0, 10))
            self.filter_entry = self._entry(top, self.filter_var, (self.f_word[0], 13))
            self.filter_entry.pack(side="left", fill="x", expand=True, ipady=7)

            btns = tk.Frame(wrap, bg=BG)
            btns.pack(side="bottom", fill="x", pady=(12, 0))
            ttk.Button(btns, text="Delete selected", command=self.delete_selected).pack(side="left")
            self.clear_btn = ttk.Button(btns, text="Clear all", command=self.clear_history)
            self.clear_btn.pack(side="left", padx=6)
            self.clear_note = tk.StringVar()
            tk.Label(btns, textvariable=self.clear_note, bg=BG, fg="#e0584c", font=self.f_small).pack(side="left", padx=8)
            tk.Label(btns, text="Double-click a phrase to look it up", bg=BG, fg=MUTED,
                     font=self.f_small).pack(side="right")

            box = tk.Frame(wrap, bg=BG)
            box.pack(fill="both", expand=True, pady=(12, 0))
            self.hist = ttk.Treeview(box, columns=("text", "added"), show="headings", selectmode="extended")
            self.hist.heading("text", text="Phrase")
            self.hist.heading("added", text="Added")
            self.hist.column("text", width=500, stretch=True)
            self.hist.column("added", width=170, stretch=False)
            sb = ttk.Scrollbar(box, orient="vertical", command=self.hist.yview)
            self.hist.configure(yscrollcommand=sb.set)
            self.hist.pack(side="left", fill="both", expand=True)
            sb.pack(side="left", fill="y")
            self.hist.bind("<Double-1>", self.on_history_double_click)
            self.hist.bind("<Delete>", lambda e: self.delete_selected())

        def refresh_history(self) -> None:
            query = self.filter_var.get().strip().casefold()
            self.hist.delete(*self.hist.get_children())
            self.shown_history = []
            for entry in reversed(self.store.history):
                if query and query not in entry["text"].casefold():
                    continue
                self.shown_history.append(entry)
                self.hist.insert("", "end", iid=str(len(self.shown_history) - 1),
                                 values=(entry["text"], entry["added"][:16].replace("T", " ")))
            total = len(self.store.history)
            self.count_var.set(f"{total} phrase{'s' if total != 1 else ''} in history")

        def on_history_double_click(self, _event=None) -> None:
            sel = self.hist.selection()
            if sel:
                text = self.shown_history[int(sel[0])]["text"]
                self.entry_var.set(text)
                self.show_tab("word")
                self.calculate(text=text, add=False)

        def delete_selected(self) -> None:
            sel = self.hist.selection()
            if sel:
                self.store.remove([self.shown_history[int(i)] for i in sel])
                self.refresh_history()
                self._refresh_views()

        def clear_history(self) -> None:
            """Click 1: the button greys out for 5 s next to an 'Are you sure?' note.
            Then it turns red and can be clicked again to really delete everything."""
            if self.clear_state == "ready":
                self._disarm()
                self.store.clear()
                self.refresh_history()
                self._refresh_views()
                self.flash("History deleted.")
                return
            if self.clear_state != "idle" or not self.store.history:
                return
            self.clear_state = "cooling"
            self.clear_btn.state(["disabled"])
            self._cooldown(5)

        def _cooldown(self, left: int) -> None:
            if self.clear_state != "cooling":
                return
            if left > 0:
                self.clear_note.set(f"Are you sure?  You can confirm in {left}s")
                self._clear_job = self.after(1000, lambda: self._cooldown(left - 1))
                return
            self.clear_state = "ready"
            self.clear_btn.state(["!disabled"])
            self.clear_btn.configure(style="Danger.TButton")
            self.clear_note.set("Are you sure?  Click Clear all again to delete everything.")
            self._clear_job = self.after(10000, self._disarm)          # gives up if you don't confirm

        def _disarm(self) -> None:
            """Back to the normal 'Clear all' button."""
            self.clear_state = "idle"
            if self._clear_job:
                try:
                    self.after_cancel(self._clear_job)
                except tk.TclError:
                    pass
                self._clear_job = None
            try:
                self.clear_btn.state(["!disabled"])
                self.clear_btn.configure(text="Clear all", style="TButton")
                self.clear_note.set("")
            except (tk.TclError, AttributeError):
                pass

        # ---- import / export ------------------------------------------------
        def export_history(self) -> None:
            if not self.store.history:
                self.flash("Nothing to export yet — your history is empty.")
                return
            path = filedialog.asksaveasfilename(
                parent=self, title="Export history", defaultextension=".txt", initialfile="gematria_history.txt",
                filetypes=[("Text file (one phrase per line)", "*.txt")])
            if path:
                self.export_history_to(path)

        def export_history_to(self, path) -> None:
            path = Path(path)                               # exports are always plain text, one phrase per line
            if path.suffix.lower() in (".json", ".csv"):
                path = path.with_suffix(".txt")
            elif path.suffix.lower() != ".txt":
                path = path.with_name(path.name + ".txt")
            try:
                count = self.store.export_file(path)
            except OSError as err:
                self.flash(f"Couldn't export: {err.strerror or err}")
                return
            self.flash(f"Exported {count} phrase{'s' if count != 1 else ''} to {path}")

        def import_history(self) -> None:
            path = filedialog.askopenfilename(
                parent=self, title="Import history",
                filetypes=[("History files", "*.json *.csv *.txt"), ("All files", "*.*")])
            if path:
                self.import_history_from(path)

        def import_history_from(self, path) -> None:
            try:
                added, skipped = self.store.import_file(path)
            except (OSError, ValueError) as err:
                self.flash(f"Couldn't import that file: {getattr(err, 'strerror', None) or err}")
                return
            note = f"Imported {added} new phrase{'s' if added != 1 else ''}"
            if skipped:
                note += f" ({skipped} already in your history)"
            self.flash(note)
            self.refresh_history()
            self._refresh_views()

        # ================= copy ==============================================
        def copy_results(self) -> None:
            lines: list[str] = []
            if self.active == "word" and self.current_text:
                totals = all_totals(self.current_text)
                lines.append(f"“{self.current_text}”")
                for name in self.enabled_names(self.current_text):
                    same = self.current_matches.get(name, [])
                    lines.append(f"{name}: {totals[name]}" + (f"   (same as: {', '.join(same)})" if same else ""))
            elif self.active == "number" and self.number_query is not None:
                lines.append(f"Phrases with the value {self.number_query}")
                for name, words in getattr(self, "number_hits", {}).items():
                    lines.append(f"{name}: {', '.join(words)}")
            elif self.active == "history":
                lines = [e["text"] for e in self.shown_history]
            if not lines:
                self.flash("Nothing to copy yet.")
                return
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.flash("Copied to the clipboard.")

        # ================= pop-up windows ====================================
        def _dialog(self, title: str, size: str):
            win = tk.Toplevel(self, bg=BG)
            win.title(title)
            w, h = (int(v) for v in size.split("x"))
            x = self.winfo_rootx() + max(0, (self.winfo_width() - w) // 2)
            y = self.winfo_rooty() + max(0, (self.winfo_height() - h) // 3)
            win.geometry(f"{w}x{h}+{x}+{y}")
            win.transient(self)
            win.update_idletasks()
            self._dark_titlebar(win, self.theme_name != "light")
            return win

        def _fit(self, win, min_width: int) -> None:
            """Make a pop-up exactly tall enough for everything in it, centred over the main window."""
            win.update_idletasks()
            w = max(win.winfo_reqwidth(), min_width)
            h = min(win.winfo_reqheight() + 12, self.winfo_screenheight() - 80)
            x = self.winfo_rootx() + max(0, (self.winfo_width() - w) // 2)
            y = self.winfo_rooty() + max(0, (self.winfo_height() - h) // 3)
            win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

        # ---- ciphers
        def open_ciphers(self) -> None:
            if self.cipher_win and self.cipher_win.winfo_exists():
                self.cipher_win.lift()
                return
            win = self.cipher_win = self._dialog("Ciphers", "660x600")
            tk.Label(win, text="Choose which ciphers are calculated and matched.", bg=BG, fg=MUTED,
                     font=self.f_small).pack(anchor="w", padx=20, pady=(16, 8))
            btns = tk.Frame(win, bg=BG)
            btns.pack(side="bottom", fill="x", padx=20, pady=16)
            ttk.Button(btns, text="Select all", command=lambda: self.set_all_ciphers(True)).pack(side="left")
            ttk.Button(btns, text="Select none", command=lambda: self.set_all_ciphers(False)).pack(side="left", padx=6)
            ttk.Button(btns, text="Done", style="Accent.TButton", command=win.destroy).pack(side="right")
            cols = tk.Frame(win, bg=BG)
            cols.pack(fill="both", expand=True, padx=20)
            for script, label in SCRIPT_LABELS.items():
                col = tk.Frame(cols, bg=BG)
                col.pack(side="left", anchor="n", padx=(0, 28))
                tk.Label(col, text=label.upper(), bg=BG, fg=MUTED,
                         font=(self.f_small[0], 9, "bold")).pack(anchor="w", pady=(0, 6))
                for name, (s, _) in CIPHERS.items():
                    if s == script:
                        ttk.Checkbutton(col, text=name, variable=self.cipher_vars[name],
                                        command=self.on_ciphers_changed).pack(anchor="w", pady=2)
            self._fit(win, 660)

        def set_all_ciphers(self, state: bool) -> None:
            for var in self.cipher_vars.values():
                var.set(state)
            self.on_ciphers_changed()

        def on_ciphers_changed(self) -> None:
            self.settings.disabled = {n for n, v in self.cipher_vars.items() if not v.get()}
            self.settings.save()
            self._refresh_views()

        # ---- colours and light/dark mode
        def open_colors(self) -> None:
            if self.color_win and self.color_win.winfo_exists():
                self.color_win.lift()
                return
            win = self.color_win = self._dialog("Colors", "540x560")
            tk.Label(win, text="Accent colour", bg=BG, fg=TEXT, font=self.f_head).pack(anchor="w", padx=24, pady=(18, 0))
            tk.Label(win, text="Used for highlights, matches, buttons and the active tab.", bg=BG, fg=MUTED,
                     font=self.f_small).pack(anchor="w", padx=24)
            grid = tk.Frame(win, bg=BG)
            grid.pack(padx=18, pady=8)
            self.swatches = {}
            for i, (name, color) in enumerate(PALETTE):
                cell = tk.Frame(grid, bg=BG)
                cell.grid(row=i // 6, column=i % 6, padx=6, pady=6)
                swatch = tk.Frame(cell, bg=color, width=48, height=40, highlightthickness=3,
                                  highlightbackground=BG, cursor="hand2")
                swatch.pack()
                tk.Label(cell, text=name, bg=BG, fg=MUTED, font=(self.f_small[0], 9)).pack(pady=(3, 0))
                swatch.bind("<Button-1>", lambda e, c=color: self.set_accent(c))
                self.swatches[color] = swatch

            tk.Label(win, text="Mode", bg=BG, fg=TEXT, font=self.f_head).pack(anchor="w", padx=24, pady=(14, 0))
            tk.Label(win, text="Light, grey (the default), or dark.", bg=BG, fg=MUTED,
                     font=self.f_small).pack(anchor="w", padx=24)
            modes = tk.Frame(win, bg=BG)
            modes.pack(pady=10)
            self.mode_canvases = {}
            for mode, label in (("light", "Light"), ("grey", "Grey"), ("black", "Dark")):
                cell = tk.Frame(modes, bg=BG)
                cell.pack(side="left", padx=26)
                circle = tk.Canvas(cell, width=52, height=52, bg=BG, highlightthickness=0, cursor="hand2")
                circle.pack()
                tk.Label(cell, text=label, bg=BG, fg=MUTED, font=(self.f_small[0], 9)).pack(pady=(3, 0))
                circle.bind("<Button-1>", lambda e, m=mode: self.set_mode(m))
                self.mode_canvases[mode] = circle

            btns = tk.Frame(win, bg=BG)
            btns.pack(side="bottom", fill="x", padx=24, pady=16)
            ttk.Button(btns, text="Custom colour…", command=self.pick_custom_color).pack(side="left")
            ttk.Button(btns, text="Reset", command=self.reset_colors).pack(side="left", padx=6)
            ttk.Button(btns, text="Done", style="Accent.TButton", command=win.destroy).pack(side="right")
            self._paint_swatches()
            self._paint_modes()
            self._fit(win, 540)

        def _paint_swatches(self) -> None:
            for color, swatch in self.swatches.items():
                try:
                    swatch.configure(highlightbackground=TEXT if color.lower() == self.accent.lower() else BG)
                except tk.TclError:
                    pass

        def _paint_modes(self) -> None:
            """Three circles: light, grey and dark. The chosen one gets a ring."""
            looks = {"light": (THEMES["light"]["BG"], "#9aa1ad"),
                     "grey": (THEMES["grey"]["PANEL"], "#4a5160"),
                     "black": (THEMES["black"]["BG"], "#5a606c")}
            for mode, c in self.mode_canvases.items():
                try:
                    c.delete("all")
                except tk.TclError:
                    continue
                fill, outline = looks[mode]
                c.create_oval(8, 8, 44, 44, fill=fill, outline=outline, width=2)
                if self.settings.mode == mode:
                    c.create_oval(3, 3, 49, 49, outline=TEXT, width=3)

        def reset_colors(self) -> None:
            """Default amber accent and the default grey mode."""
            self.set_accent(DEFAULT_ACCENT)
            self.set_mode("grey")

        def pick_custom_color(self) -> None:
            _, chosen = colorchooser.askcolor(color=self.accent, parent=self.color_win, title="Pick a colour")
            if chosen:
                self.set_accent(chosen)

        def set_accent(self, color: str) -> None:
            self.accent = color
            self.settings.accent = color
            self.settings.save()
            self._style()
            self._refresh_accent_colors()
            self._refresh_views()
            self._paint_swatches()

        def _refresh_accent_colors(self) -> None:
            """Re-apply the accent wherever it is used as a text/border colour."""
            self.accent_fg = readable(self.accent, PANEL)
            self._paint_tabs()
            for e in self.accent_entries:
                e.configure(highlightcolor=self.accent_fg, insertbackground=self.accent_fg)
            self.note_label.configure(fg=self.accent_fg)

        def set_mode(self, mode: str) -> None:
            self.settings.mode = mode
            self.settings.save()
            self.apply_theme(mode)
            self._paint_modes()

        def apply_theme(self, name: str) -> None:
            if name == self.theme_name:
                return
            old, new = THEMES[self.theme_name], THEMES[name]
            set_theme(name)
            self.theme_name = name
            self._clear_detail()
            self._style()
            self._retheme({old[r].lower(): new[r] for r in THEME_ROLES})
            if self.logo_label is not None:
                self.logo_label.configure(image=self.logo_imgs["light" if name == "light" else "dark"])
            self._refresh_accent_colors()
            self._refresh_views()
            self._paint_swatches()
            self._paint_modes()
            for win in (self, self.cipher_win, self.color_win):
                if win is not None and win.winfo_exists():
                    self._dark_titlebar(win, name != "light")

        def _retheme(self, mapping: dict[str, str]) -> None:
            """Walk every widget and swap old theme colours for the new ones."""
            options = ("bg", "fg", "highlightbackground", "highlightcolor", "insertbackground",
                       "selectbackground", "selectforeground", "activebackground", "activeforeground")

            def walk(w) -> None:
                for opt in options:
                    try:
                        current = str(w.cget(opt)).lower()
                    except tk.TclError:                      # option not supported (e.g. ttk widgets)
                        continue
                    if current in mapping:
                        try:
                            w.configure(**{opt: mapping[current]})
                        except tk.TclError:
                            pass
                for child in w.winfo_children():
                    walk(child)

            walk(self)

    App(Store(key=phrase_key), Settings()).mainloop()


# ==========================================================================
# COMMAND LINE (optional)
# ==========================================================================

def cli(phrases: list[str], show_breakdown: bool) -> None:
    store = Store(key=phrase_key)
    if len(phrases) == 2:
        a, b = phrases
        names = [n for n in CIPHERS if n in applicable_ciphers(a) and n in applicable_ciphers(b)]
        print(f'\n  A: "{a}"\n  B: "{b}"\n  ' + "-" * 50)
        for n in names:
            ta, tb = all_totals(a)[n], all_totals(b)[n]
            print(f"  {n:<24}{ta:>7} vs {tb:<7}{'  <-- MATCH' if ta == tb and ta else ''}")
        return
    text = phrases[0]
    names = applicable_ciphers(text)
    matches = find_matches(text, store.history, names)
    print(f'\n  "{text}"\n  ' + "-" * 50)
    for n in names:
        total = all_totals(text)[n]
        line = f"  {n:<24}{total:>8}   (root {digital_root(total)})"
        if matches[n]:
            line += "   same as: " + ", ".join(matches[n][:5])
        print(line)
        if show_breakdown:
            print("      " + " + ".join(f"{c}={v}" for c, v in breakdown(text, n)))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ginseng, a gematria calculator (no arguments = open the window)")
    parser.add_argument("phrases", nargs="*", help="one phrase to calculate, or two to compare")
    parser.add_argument("-b", "--breakdown", action="store_true", help="show letter-by-letter values")
    parser.add_argument("--list", action="store_true", help="list all ciphers")
    args = parser.parse_args()

    if args.list:
        for script, label in SCRIPT_LABELS.items():
            print(f"\n{label}")
            for name, (s, _) in CIPHERS.items():
                if s == script:
                    print(f"  {name}")
        return
    if not args.phrases:
        run_gui()
    elif len(args.phrases) <= 2:
        cli(args.phrases, args.breakdown)
    else:
        sys.exit("Give one phrase to calculate, or two to compare.")


if __name__ == "__main__":
    main()
