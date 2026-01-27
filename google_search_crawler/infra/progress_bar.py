from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from typing import Mapping, TextIO


def build_progress_bar(
    *,
    filled: int,
    total: int,
    head_len: int = 2,
    full_block: str = "\u2593",
    mid_block: str = "\u2592",
    light_block: str = "\u2591",
) -> str:
    if total <= 0:
        total = 0
    filled = max(0, min(filled, total))
    head = min(head_len, max(total - filled, 0))
    empty = max(total - filled - head, 0)
    return (full_block * filled) + (mid_block * head) + (light_block * empty)


def _get_terminal_columns(stream: TextIO) -> int:
    fileno = getattr(stream, "fileno", None)
    if callable(fileno):
        try:
            return int(os.get_terminal_size(fileno()).columns)
        except Exception:
            pass
    return int(shutil.get_terminal_size(fallback=(80, 20)).columns)


@dataclass(slots=True)
class ProgressLineWriter:
    prefix: str
    total: int
    width: int = 0
    head_len: int = 2
    stream: TextIO = sys.stderr
    enabled: bool | None = None

    _last_len: int = field(init=False, default=0)
    _last_filled: int = field(init=False, default=-1)

    def __post_init__(self) -> None:
        if self.width > 0:
            return
        columns = _get_terminal_columns(self.stream)
        self.width = max(10, columns // 4)

    def is_enabled(self) -> bool:
        if self.enabled is not None:
            return self.enabled
        isatty = getattr(self.stream, "isatty", None)
        if callable(isatty):
            try:
                return bool(isatty())
            except Exception:
                return False
        return False

    def update(
        self,
        current: int,
        *,
        counters: Mapping[str, int] | None = None,
        suffix: str | None = None,
        force: bool = False,
    ) -> None:
        if not self.is_enabled():
            return

        total = max(int(self.total), 0)
        current_int = max(int(current), 0)
        if total > 0:
            current_int = min(current_int, total)

        filled = 0 if total <= 0 else min(int(self.width * (current_int / total)), self.width)

        should_write = force or current_int == 0 or current_int == total or filled != self._last_filled
        if not should_write:
            return

        bar = build_progress_bar(filled=filled, total=self.width, head_len=self.head_len)
        label_parts: list[str] = []
        if counters:
            label_parts.extend([f"{key}={value}" for key, value in counters.items()])
        if suffix:
            label_parts.append(suffix)

        label = " ".join(label_parts)
        line = f"{self.prefix} [{bar}] {current_int}/{total}"
        if label:
            line = f"{line} {label}"

        padded = line.ljust(self._last_len)
        self.stream.write("\r" + padded)
        self.stream.flush()
        self._last_len = len(line)
        self._last_filled = filled

    def finish(
        self,
        *,
        counters: Mapping[str, int] | None = None,
        suffix: str | None = None,
    ) -> None:
        if not self.is_enabled():
            return
        self.update(self.total, counters=counters, suffix=suffix, force=True)
        self.stream.write("\n")
        self.stream.flush()
