"""Use case: compare installed mods with their official packages and restore missing files."""
from __future__ import annotations

import zipfile

from ..domain import layout
from ..domain.models import InstalledMod, VerifyResult
from ..ports import PackageRegistry, ProfileRepository


class VerifyService:
    def __init__(self, profiles: ProfileRepository, registry: PackageRegistry):
        self.profiles = profiles
        self.registry = registry

    def verify_profile(self, profile: str, fix: bool = False, only: str | None = None) -> list[VerifyResult]:
        return [self.verify_mod(m, fix) for m in self.profiles.installed_mods(profile)
                if not only or only.lower() in m.full_name.lower()]

    def verify_mod(self, mod: InstalledMod, fix: bool = False) -> VerifyResult:
        result = VerifyResult(mod.full_name, mod.version)
        if mod.local:
            result.skipped_reason = "mod local (no está en Thunderstore)"
            return result
        if mod.version == "?" or not mod.folders:
            result.skipped_reason = "sin manifest.json; no se puede comparar"
            return result
        try:
            zip_path = self.registry.download(mod.ref)
        except Exception as e:  # noqa: BLE001 - network problems are reported, not raised
            result.skipped_reason = f"no se pudo descargar el paquete: {e}"
            return result

        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                member = layout.normalise(info.filename)
                if not layout.should_check(member):
                    continue
                if any(self.profiles.file_exists(mod, c) for c in layout.candidate_paths(member)):
                    continue
                kind, relative = layout.restore_target(member)
                if fix and self.profiles.write_mod_file(mod, kind, relative, z.read(info)):
                    result.restored.append(member)
                else:
                    result.missing.append(member)
        return result
