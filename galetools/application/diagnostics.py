"""Use case: understand the last game session of a profile from its BepInEx log."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.logparse import parse_log
from ..domain.models import LogSummary
from ..ports import ProfileRepository


@dataclass
class Diagnosis:
    summary: LogSummary
    log_found: bool
    not_loaded: list[str] = field(default_factory=list)  # enabled mods that never showed up in the log


class DiagnosticsService:
    def __init__(self, profiles: ProfileRepository):
        self.profiles = profiles

    def diagnose(self, profile: str) -> Diagnosis:
        text = self.profiles.read_log(profile)
        summary = parse_log(text or "")
        d = Diagnosis(summary, text is not None)
        if summary.manifests:
            loaded = {k.lower() for k in summary.manifests}
            d.not_loaded = [m.full_name for m in self.profiles.installed_mods(profile)
                            if m.enabled and m.has_plugin_code and m.full_name.lower() not in loaded]
        return d
