"""PackageRegistry adapter: Thunderstore HTTP API with an on-disk cache."""
from __future__ import annotations

import json
import time
import urllib.request
import zipfile
from pathlib import Path

from ..config import Settings
from ..domain.errors import GaleToolsError
from ..domain.models import PackageInfo, PackageRef

BASE = "https://thunderstore.io"


class ThunderstoreRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._index: list[PackageInfo] | None = None

    def _get(self, url: str, timeout: int = 120) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": self.settings.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def info(self, ref: PackageRef) -> PackageInfo:
        try:
            data = json.loads(self._get(f"{BASE}/api/experimental/package/{ref.owner}/{ref.name}/"))
        except Exception as e:  # noqa: BLE001
            raise GaleToolsError(f"No encuentro {ref.full_name} en Thunderstore ({e}).")
        latest = data["latest"]
        return PackageInfo(
            ref=PackageRef(data["namespace"], data["name"]),
            latest_version=latest["version_number"],
            description=latest.get("description", ""),
            categories=_categories(data),
            downloads=data.get("total_downloads", 0) or 0,
            date_updated=data.get("date_updated", ""),
            deprecated=bool(data.get("is_deprecated")),
        )

    def all_packages(self) -> list[PackageInfo]:
        if self._index is None:
            path = self.settings.tools_home / "cache" / f"{self.settings.game_slug}_packages.json"
            if not path.is_file() or time.time() - path.stat().st_mtime > self.settings.index_max_age:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self._get(f"{BASE}/c/{self.settings.game_slug}/api/v1/package/", timeout=600))
            raw = json.loads(path.read_text(encoding="utf-8"))
            self._index = [_from_listing(p) for p in raw if p.get("versions")]
        return self._index

    def download(self, ref: PackageRef) -> Path:
        if not ref.version:
            raise GaleToolsError(f"Hace falta una versión para descargar {ref.full_name}.")
        dest = self.settings.tools_home / "downloads" / str(ref) / "package.zip"
        if not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(self._get(f"{BASE}/package/download/{ref.owner}/{ref.name}/{ref.version}/", timeout=600))
        if not zipfile.is_zipfile(dest):
            dest.unlink(missing_ok=True)
            raise GaleToolsError(f"La descarga de {ref} no es un zip válido.")
        return dest


def _categories(data: dict) -> list[str]:
    """Categories as the experimental API exposes them (shape varies), or an empty list."""
    try:
        found: list[str] = []
        for listing in data.get("community_listings") or []:
            for c in listing.get("categories") or []:
                found.append(c if isinstance(c, str) else str(c.get("name", "")))
        return [c for c in found if c]
    except (AttributeError, TypeError):
        return []


def _from_listing(p: dict) -> PackageInfo:
    latest = p["versions"][0]
    return PackageInfo(
        ref=PackageRef(p["owner"], p["name"]),
        latest_version=latest["version_number"],
        description=latest.get("description", ""),
        categories=list(p.get("categories") or []),
        downloads=sum(v.get("downloads", 0) for v in p["versions"]),
        date_updated=p.get("date_updated", ""),
        deprecated=bool(p.get("is_deprecated")),
    )
