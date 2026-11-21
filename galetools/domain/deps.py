"""Dependency resolution between installed mods. Pure functions."""
from __future__ import annotations

from typing import Iterable

from .models import InstalledMod

# Libraries every load test needs.
CORE_LIBRARIES = ("bbepis-BepInExPack", "RiskofThunder-RoR2BepInExPack", "RiskofThunder-HookGenPatcher",
                  "RiskofThunder-FixPluginTypesSerialization", "pseudopulse-SeekersPatcher")
# Mods that only add the console window; left out of automated tests.
TEST_EXCLUDED = ("RiskofThunder-BepInEx_GUI",)


def dependency_closure(mods: list[InstalledMod], wanted: Iterable[str],
                       always: Iterable[str] = CORE_LIBRARIES,
                       excluded: Iterable[str] = TEST_EXCLUDED) -> list[InstalledMod]:
    """The wanted mods plus everything they depend on (transitively), in profile order."""
    by_name = {m.full_name.lower(): m for m in mods}
    excluded_l = {e.lower() for e in excluded}
    chosen: set[str] = set()
    stack = [w.lower() for w in (*wanted, *always)]
    while stack:
        key = stack.pop()
        mod = by_name.get(key)
        if mod is None or key in chosen or key in excluded_l:
            continue
        chosen.add(key)
        stack.extend(d.lower() for d in mod.dependency_names)
    return [m for m in mods if m.full_name.lower() in chosen]


def candidates_for_testing(mods: list[InstalledMod]) -> list[InstalledMod]:
    """Enabled mods that make sense to test on their own (not core libraries or excluded ones)."""
    skip = {n.lower() for n in (*CORE_LIBRARIES, *TEST_EXCLUDED)}
    return [m for m in mods if m.enabled and m.full_name.lower() not in skip]
