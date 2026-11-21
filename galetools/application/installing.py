"""Use cases that change the user's setup through Gale: install, import, launch."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain import scanrules
from ..domain.errors import GaleToolsError
from ..domain.models import PackageRef, ScanReport
from ..ports import ModManager, ProfileRepository
from .catalog import CatalogService
from .scanning import ScanService


@dataclass
class InstallOutcome:
    ref: PackageRef
    profile: str | None
    scan: ScanReport | None
    installed: bool


class InstallService:
    def __init__(self, catalog: CatalogService, manager: ModManager, scanner: ScanService, profiles: ProfileRepository):
        self.catalog = catalog
        self.manager = manager
        self.scanner = scanner
        self.profiles = profiles

    def _check_profile(self, profile: str | None) -> None:
        if profile and profile not in self.profiles.list_profiles():
            raise GaleToolsError(f"No existe el perfil '{profile}'. Perfiles: " + ", ".join(self.profiles.list_profiles()))

    def install(self, ref: PackageRef, profile: str | None, scan_first: bool = True) -> InstallOutcome:
        """Scans first (unless disabled) and refuses if the antivirus flags the package."""
        self._check_profile(profile)
        ref, _ = self.catalog.resolve(ref)
        report = self.scanner.scan(ref) if scan_first else None
        if report and scanrules.malware_detected(report.malware_scan):
            return InstallOutcome(ref, profile, report, installed=False)
        if profile:
            self.manager.select_profile(profile)
        self.manager.install_package(ref)
        return InstallOutcome(ref, profile, report, installed=True)

    def install_local(self, path: Path, profile: str | None) -> Path:
        self._check_profile(profile)
        path = path.expanduser().resolve()
        if not path.is_file():
            raise GaleToolsError(f"No existe el archivo {path}")
        self.manager.install_local(path, profile)
        return path

    def launch(self, profile: str | None, vanilla: bool) -> None:
        self._check_profile(profile)
        self.manager.launch(profile, vanilla)
