"""Use cases about the Thunderstore catalog and the user's profiles."""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.errors import GaleToolsError
from ..domain.models import InstalledMod, PackageInfo, PackageRef
from ..ports import GameRunner, ModManager, PackageRegistry, ProfileRepository


class CatalogService:
    def __init__(self, registry: PackageRegistry):
        self.registry = registry

    def search(self, query: str, limit: int = 15, include_deprecated: bool = False) -> tuple[int, list[PackageInfo]]:
        words = query.lower().split()
        hits = [p for p in self.registry.all_packages()
                if (include_deprecated or not p.deprecated)
                and all(w in (p.ref.full_name + " " + p.description).lower() for w in words)]
        hits.sort(key=lambda p: p.downloads, reverse=True)
        return len(hits), hits[:limit]

    def resolve(self, ref: PackageRef) -> tuple[PackageRef, PackageInfo]:
        """Canonical owner/name casing and an exact version (the latest if none was given)."""
        info = self.registry.info(ref)
        return info.ref.with_version(ref.version or info.latest_version), info


@dataclass
class Status:
    gale_running: bool
    game_running: bool
    game_dir: str
    profiles: list[str]


class ProfileService:
    def __init__(self, profiles: ProfileRepository, manager: ModManager, game: GameRunner):
        self.profiles = profiles
        self.manager = manager
        self.game = game

    def status(self) -> Status:
        try:
            game_dir = str(self.game.game_dir())
        except GaleToolsError as e:
            game_dir = str(e)
        return Status(self.manager.is_running(), bool(self.game.running_pids()), game_dir, self.profiles.list_profiles())

    def mods(self, profile: str) -> list[InstalledMod]:
        return self.profiles.installed_mods(profile)

    def find(self, profile: str, name: str) -> InstalledMod:
        mods = self.mods(profile)
        name_l = name.lower()
        exact = [m for m in mods if m.full_name.lower() == name_l]
        if exact:
            return exact[0]
        partial = [m for m in mods if name_l in m.full_name.lower()]
        if len(partial) == 1:
            return partial[0]
        if not partial:
            raise GaleToolsError(f"No hay ningún mod '{name}' en el perfil '{profile}'.")
        raise GaleToolsError(f"'{name}' es ambiguo: " + ", ".join(m.full_name for m in partial))
