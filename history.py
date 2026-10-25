"""
History storage for Ginseng.

Keeps the list of phrases you've entered, saves them to disk, and can import
and export them. This module knows nothing about ciphers, so it can be reused
or tested on its own.

    store = Store()                       # loads ~/.gematria_calculator.json
    store.add("hello world")              # True if new, False if already there
    store.export_file("backup.csv")       # .json, .csv or .txt
    store.import_file("backup.csv")       # -> (added, skipped)

Each entry is a dict:  {"text": "hello world", "added": "2026-10-24T14:30:00"}
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

DEFAULT_PATH = Path(os.environ.get("GEMATRIA_DATA", Path.home() / ".gematria_calculator.json"))

HEADER_NAMES = {"phrase", "text", "word", "words"}


def default_key(text: str) -> str:
    """Identity of a phrase when no custom key is given: letters/digits only, case-insensitive."""
    return "".join(c for c in text.casefold() if c.isalnum())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean(text) -> str:
    return " ".join(str(text).split())


class Store:
    """The history. Entries are kept oldest first in `self.history`."""

    def __init__(self, path: Path = DEFAULT_PATH, key: Callable[[str], str] = default_key):
        self.path = Path(path)
        self.key = key
        self.history: list[dict] = []
        self.load()

    # ---- saving and loading ----------------------------------------------
    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.history = self._parse_entries(data.get("history", []) if isinstance(data, dict) else [])

    def save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"history": self.history}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    @staticmethod
    def _parse_entries(items) -> list[dict]:
        """Accept a list of strings or of {"text", "added"} dicts."""
        entries = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text, added = _clean(item["text"]), str(item.get("added") or "")
            elif isinstance(item, str):
                text, added = _clean(item), ""
            else:
                continue                      # numbers, nulls, malformed entries are ignored
            if text:
                entries.append({"text": text, "added": added or _now()})
        return entries

    # ---- editing ------------------------------------------------------------
    def has(self, text: str) -> bool:
        key = self.key(text)
        return bool(key) and any(self.key(e["text"]) == key for e in self.history)

    def add(self, text: str, added: Optional[str] = None, save: bool = True) -> bool:
        """Add a phrase unless it's already there. Returns True if it was added."""
        text = _clean(text)
        if not self.key(text) or self.has(text):
            return False
        self.history.append({"text": text, "added": added or _now()})
        if save:
            self.save()
        return True

    def remove(self, entries: list[dict]) -> None:
        ids = {id(e) for e in entries}
        self.history = [e for e in self.history if id(e) not in ids]
        self.save()

    def clear(self) -> None:
        self.history = []
        self.save()

    # ---- export ---------------------------------------------------------------
    def export_file(self, path, columns: Optional[dict[str, Callable[[str], object]]] = None) -> int:
        """Write the history to `path`. The format follows the extension:
        .csv (opens in Excel), .txt (one phrase per line), anything else = JSON.
        `columns` adds extra CSV columns: {"Ordinal": lambda text: value, ...}.
        Returns the number of phrases written."""
        path = Path(path)
        ext = path.suffix.lower()
        if ext == ".csv":
            columns = columns or {}
            with open(path, "w", encoding="utf-8-sig", newline="") as f:   # BOM so Excel reads Hebrew/Greek
                writer = csv.writer(f)
                writer.writerow(["Phrase", "Added", *columns])
                for e in self.history:
                    writer.writerow([e["text"], e["added"], *(fn(e["text"]) for fn in columns.values())])
        elif ext == ".txt":
            path.write_text("\n".join(e["text"] for e in self.history) + "\n", encoding="utf-8")
        else:
            payload = {"app": "gematria-calculator", "version": 1, "history": self.history}
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        return len(self.history)

    # ---- import ---------------------------------------------------------------
    def import_file(self, path) -> tuple[int, int]:
        """Merge phrases from a .json, .csv or .txt file into the history.
        Phrases already present are skipped, nothing is overwritten.
        Returns (added, skipped). Raises ValueError / OSError if the file can't be read."""
        path = Path(path)
        text = path.read_text(encoding="utf-8-sig")
        ext = path.suffix.lower()
        if ext == ".json":
            try:
                data = json.loads(text)
            except ValueError:
                raise ValueError("this doesn't look like a valid history file") from None
            items = data.get("history", []) if isinstance(data, dict) else data
            incoming = self._parse_entries(items)
            if not incoming and items:
                raise ValueError("no phrases found in this JSON file")
        elif ext == ".csv":
            rows = [r for r in csv.reader(text.splitlines()) if r and r[0].strip()]
            if rows and rows[0][0].strip().casefold() in HEADER_NAMES:
                rows = rows[1:]
            incoming = []
            for r in rows:
                added = r[1].strip() if len(r) > 1 else ""
                try:
                    datetime.fromisoformat(added)
                except ValueError:
                    added = ""
                incoming.append({"text": _clean(r[0]), "added": added or _now()})
        else:
            lines = (ln.strip() for ln in text.splitlines())
            incoming = [{"text": _clean(ln), "added": _now()} for ln in lines if ln and not ln.startswith("#")]

        added = skipped = 0
        for e in incoming:
            if self.add(e["text"], e["added"], save=False):
                added += 1
            else:
                skipped += 1
        if added:
            self.history.sort(key=lambda e: e["added"])     # stable: keeps file order for equal times
            self.save()
        return added, skipped
