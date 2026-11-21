"""Composition root: the only place that knows which adapter implements each port."""
from __future__ import annotations

from dataclasses import dataclass

from .adapters.gale_cli import GaleCli
from .adapters.gale_profiles import GaleProfileRepository
from .adapters.security import DefenderScanner, IlSpyDecompiler, JsonFileCache
from .adapters.steam_game import SteamGameRunner
from .adapters.thunderstore import ThunderstoreRegistry
from .adapters.windows import SystemClock
from .application.catalog import CatalogService, ProfileService
from .application.diagnostics import DiagnosticsService
from .application.installing import InstallService
from .application.loadtest import LoadTestService
from .application.scanning import ScanService
from .application.verification import VerifyService
from .config import Settings


@dataclass
class App:
    settings: Settings
    catalog: CatalogService
    profiles: ProfileService
    scanner: ScanService
    installer: InstallService
    verifier: VerifyService
    diagnostics: DiagnosticsService
    loadtests: LoadTestService


def build_app(settings: Settings | None = None) -> App:
    settings = settings or Settings.from_env()
    profiles_repo = GaleProfileRepository(settings)
    registry = ThunderstoreRegistry(settings)
    manager = GaleCli(settings)
    game = SteamGameRunner(settings)

    catalog = CatalogService(registry)
    scanner = ScanService(catalog, registry, IlSpyDecompiler(settings), DefenderScanner())
    return App(
        settings=settings,
        catalog=catalog,
        profiles=ProfileService(profiles_repo, manager, game),
        scanner=scanner,
        installer=InstallService(catalog, manager, scanner, profiles_repo),
        verifier=VerifyService(profiles_repo, registry),
        diagnostics=DiagnosticsService(profiles_repo),
        loadtests=LoadTestService(profiles_repo, game, JsonFileCache(settings), SystemClock()),
    )
