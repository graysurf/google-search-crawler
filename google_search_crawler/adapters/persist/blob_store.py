"""Cold storage abstraction for artifacts (local filesystem only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class BlobStore(Protocol):
    def put_file(self, *, local_path: Path, remote_key: str) -> str: ...


@dataclass(frozen=True, slots=True)
class LocalBlobStore:
    root_dir: Path

    def put_file(self, *, local_path: Path, remote_key: str) -> str:
        dest = self.root_dir / remote_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(local_path.read_bytes())
        return str(dest)
