"""Domain entities. Pure data, no I/O."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .errors import GaleToolsError

_REF = re.compile(r"(?P<owner>.+?)-(?P<name>.+?)(?:-(?P<version>\d+\.\d+\.\d+))?")


@dataclass(frozen=True)
class PackageRef:
    """A Thunderstore package, optionally pinned to a version."""

    owner: str
    name: str
    version: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}-{self.name}"

    def __str__(self) -> str:
        return self.full_name + (f"-{self.version}" if self.version else "")

    def with_version(self, version: str) -> "PackageRef":
        return PackageRef(self.owner, self.name, version)

    @classmethod
    def parse(cls, text: str) -> "PackageRef":
        """Accepts 'Owner-Name', 'Owner-Name-1.2.3' or 'Owner/Name[/1.2.3]'."""
        text = text.strip().strip("/")
        if "/" in text:
            parts = text.split("/")
            if len(parts) < 2 or not all(parts[:2]):
                raise GaleToolsError(f"Formato de paquete no válido: '{text}'")
            return cls(parts[0], parts[1], parts[2] if len(parts) > 2 and parts[2] else None)
        m = _REF.fullmatch(text)
        if not m:
            raise GaleToolsError(f"Formato de paquete no válido: '{text}'. Usa Autor-Nombre o Autor-Nombre-1.2.3")
        return cls(m["owner"], m["name"], m["version"])


@dataclass
class PackageInfo:
    """What the registry knows about the latest version of a package."""

    ref: PackageRef
    latest_version: str
    description: str = ""
    categories: list[str] = field(default_factory=list)
    downloads: int = 0
    date_updated: str = ""
    deprecated: bool = False


@dataclass
class InstalledMod:
    """A mod inside a Gale profile. `folders` are its plugins/patchers/core folders."""

    full_name: str
    version: str
    enabled: bool = True
    folders: list[Path] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # Owner-Name-Version
    local: bool = False  # imported from a file, not from Thunderstore
    has_plugin_code: bool = False  # has a .dll inside a plugins/ folder (prints a TS manifest when loaded)

    @property
    def ref(self) -> PackageRef:
        owner, _, name = self.full_name.partition("-")
        return PackageRef(owner, name or owner, None if self.version == "?" else self.version)

    @property
    def dependency_names(self) -> list[str]:
        return [d.rsplit("-", 1)[0] for d in self.dependencies]


@dataclass
class VerifyResult:
    mod: str
    version: str
    missing: list[str] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return not self.missing and self.skipped_reason is None


@dataclass
class ScanReport:
    package: str
    files: list[str] = field(default_factory=list)
    managed: list[str] = field(default_factory=list)
    native: list[str] = field(default_factory=list)
    decompile_errors: list[str] = field(default_factory=list)
    hits: dict[str, list[str]] = field(default_factory=dict)  # rule label -> "file:line: code"
    lines_of_code: int = 0
    malware_scan: str = "no ejecutado"
    categories: list[str] = field(default_factory=list)


@dataclass
class LogSummary:
    loaded: dict[str, str] = field(default_factory=dict)      # plugin display name -> version
    manifests: dict[str, str] = field(default_factory=dict)   # Owner-Name -> version
    errors: Counter = field(default_factory=Counter)          # (level, source, message) -> count
    exceptions: list[str] = field(default_factory=list)
    chainloader_done: bool = False
    game_version_warning: str | None = None

    def error_messages(self) -> set[str]:
        return {msg for (level, _, msg) in self.errors if level in ("Error", "Fatal")}


@dataclass
class LoadTestResult:
    name: str
    mods: list[str]
    summary: LogSummary | None = None
    finished_loading: bool = False
    seconds: float = 0.0
    note: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.finished_loading and not self.errors
