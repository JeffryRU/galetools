"""Settings, read from environment variables with sensible defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


@dataclass(frozen=True)
class Settings:
    game_slug: str = "riskofrain2"
    steam_app_id: int = 632360
    default_profile: str = "Default"
    gale_data: Path = Path()
    tools_home: Path = Path()
    gale_exe: Path | None = None
    game_dir: Path | None = None
    user_agent: str = "galetools/2.0 (https://github.com/JeffryRU/galetools)"
    index_max_age: int = 6 * 3600

    @classmethod
    def from_env(cls) -> "Settings":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        localappdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return cls(
            default_profile=os.environ.get("GALETOOLS_PROFILE", "Default"),
            gale_data=_env_path("GALE_DATA") or appdata / "com.kesomannen.gale",
            # Kept short on purpose: Windows paths are limited to 260 characters.
            tools_home=_env_path("GALETOOLS_HOME") or localappdata / "galetools",
            gale_exe=_env_path("GALE_EXE"),
            game_dir=_env_path("ROR2_DIR"),
        )

    @property
    def profiles_dir(self) -> Path:
        return self.gale_data / self.game_slug / "profiles"
