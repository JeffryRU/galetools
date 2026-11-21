from pathlib import Path

import pytest

from galetools.application.catalog import CatalogService, ProfileService
from galetools.application.diagnostics import DiagnosticsService
from galetools.application.installing import InstallService
from galetools.application.loadtest import LoadTestService, LoadTestSettings
from galetools.application.scanning import ScanService
from galetools.application.verification import VerifyService
from galetools.domain.errors import GaleToolsError
from galetools.domain.models import PackageRef
from tests.fakes import (FakeAntivirus, FakeClock, FakeDecompiler, FakeGame, FakeManager, FakeProfiles,
                         FakeRegistry, MemoryCache, info, make_zip, mod)


def test_search_filters_and_sorts():
    reg = FakeRegistry([info("A-Pause", description="command pause", downloads=10),
                        info("B-Pause", description="pause in command menu", downloads=99),
                        info("C-Old", description="command pause", downloads=500, deprecated=True),
                        info("D-Other", description="nothing")])
    total, items = CatalogService(reg).search("command pause")
    assert total == 2 and [p.ref.full_name for p in items] == ["B-Pause", "A-Pause"]


def test_find_mod_partial_and_ambiguous():
    svc = ProfileService(FakeProfiles({"P": [mod("A-MiniMap"), mod("B-MiniMapFix"), mod("C-Other")]}), FakeManager(), FakeGame())
    assert svc.find("P", "other").full_name == "C-Other"
    with pytest.raises(GaleToolsError):
        svc.find("P", "minimap")


def test_verify_reports_and_restores_missing_language_files(tmp_path):
    z = make_zip(tmp_path / "ps.zip", {
        "manifest.json": b"{}", "README.md": b"",
        "plugins/ProperSave/ProperSave.dll": b"dll",
        "plugins/ProperSave/Language/en/tokens.json": b"{}",
    })
    ps = mod("KingEnderBrine-ProperSave", "3.1.3")
    profiles = FakeProfiles({"P": [ps, mod("Local", local=True)]}, files={ps.full_name: {"ProperSave/ProperSave.dll"}})
    svc = VerifyService(profiles, FakeRegistry([], {"KingEnderBrine-ProperSave-3.1.3": z}))

    results = svc.verify_profile("P")
    assert results[0].missing == ["plugins/ProperSave/Language/en/tokens.json"]
    assert results[1].skipped_reason  # local mods are skipped

    fixed = svc.verify_profile("P", fix=True)[0]
    assert fixed.restored == ["plugins/ProperSave/Language/en/tokens.json"] and fixed.ok
    assert profiles.written == [(ps.full_name, "plugins", "ProperSave/Language/en/tokens.json")]


def test_diagnostics_lists_enabled_mods_missing_from_log():
    log = "[Info   :   BepInEx] TS Manifest: A-Loaded-1.0.0\n[Message:   BepInEx] Chainloader startup complete\n"
    profiles = FakeProfiles({"P": [mod("A-Loaded"), mod("B-Missing"), mod("C-Off", enabled=False),
                                   mod("D-PatcherOnly", plugin_code=False)]}, log=log)
    d = DiagnosticsService(profiles).diagnose("P")
    assert d.not_loaded == ["B-Missing"]


def _scan_service(tmp_path, source, antivirus="Scanning found no threats."):
    z = make_zip(tmp_path / "dl" / "pkg.zip", {"plugins/Mod.dll": b"MZ", "plugins/native.dll": b"MZ", "README.md": b""})
    reg = FakeRegistry([info("A-Mod", "1.0.0")], {"A-Mod-1.0.0": z})
    dec = FakeDecompiler({"Mod": source})
    dec.is_managed = lambda p: {"Mod": True, "native": False}.get(p.stem)  # one .NET dll, one native dll
    catalog = CatalogService(reg)
    return catalog, reg, ScanService(catalog, reg, dec, FakeAntivirus(antivirus))


def test_scan_flags_native_and_risky_code(tmp_path):
    _, _, svc = _scan_service(tmp_path, "class P { void A() { Process.Start(\"cmd.exe\"); } }")
    r = svc.scan(PackageRef.parse("A-Mod"))
    assert r.package == "A-Mod-1.0.0"
    assert r.native == ["plugins\\native.dll"] or r.native == ["plugins/native.dll"]
    assert "Ejecuta programas" in r.hits and r.lines_of_code >= 1


def test_install_scans_then_sends_to_gale(tmp_path):
    catalog, reg, scanner = _scan_service(tmp_path, "class P {}")
    manager = FakeManager()
    svc = InstallService(catalog, manager, scanner, FakeProfiles({"P": []}))
    out = svc.install(PackageRef.parse("a-mod"), "P")
    assert out.installed and str(out.ref) == "A-Mod-1.0.0"
    assert manager.calls == [("select", "P"), ("install", "A-Mod-1.0.0")]


def test_install_refuses_when_antivirus_flags(tmp_path):
    catalog, reg, scanner = _scan_service(tmp_path, "class P {}", antivirus="Threat Trojan found")
    manager = FakeManager()
    out = InstallService(catalog, manager, scanner, FakeProfiles({"P": []})).install(PackageRef.parse("A-Mod"), "P")
    assert not out.installed and manager.calls == []


def test_install_rejects_unknown_profile(tmp_path):
    catalog, reg, scanner = _scan_service(tmp_path, "")
    with pytest.raises(GaleToolsError):
        InstallService(catalog, FakeManager(), scanner, FakeProfiles({"P": []})).install(PackageRef.parse("A-Mod"), "Nope")


# ---------------------------------------------------------------------------- load tests

LOADED_LOG = ("[Error  : Unity Log] base game error\n"
              "[Error  : Mod] mod error\n"
              "[Message:   BepInEx] Chainloader startup complete\n")


def _loadtest(tmp_path, log=LOADED_LOG, crash=False, never_starts=False):
    profiles = FakeProfiles({"P": [mod("bbepis-BepInExPack"), mod("A-Mod"), mod("B-Mod")]}, tmp=tmp_path)
    game, clock = FakeGame(), FakeClock()

    def tick(t):
        if never_starts:
            return
        if t >= 6 and not game.pids and not game.killed:
            game.pids = {4242}  # the game process appears
        log_path = tmp_path / profiles.last_test[0] / "BepInEx" / "LogOutput.log"
        if t >= 15:
            profiles.texts[log_path] = log
        if crash and t >= 20:
            game.pids = set()

    clock.on_sleep = tick
    return LoadTestService(profiles, game, MemoryCache(), clock), profiles, game


def test_load_test_success_closes_only_its_game(tmp_path):
    svc, profiles, game = _loadtest(tmp_path)
    r = svc.run("P", ["A-Mod"], settings=LoadTestSettings(settle_seconds=10))
    assert r.finished_loading and game.killed == {4242}
    assert profiles.last_test[1] == ["bbepis-BepInExPack", "A-Mod"]  # profile order
    assert any("mod error" in e for e in r.errors)


def test_load_test_refuses_if_game_open(tmp_path):
    svc, _, game = _loadtest(tmp_path)
    game.pids = {1}
    with pytest.raises(GaleToolsError):
        svc.run("P", [])


def test_load_test_detects_crash_and_start_timeout(tmp_path):
    svc, _, _ = _loadtest(tmp_path, log="[Info   : X] still loading\n", crash=True)
    assert "crash" in svc.run("P", [], settings=LoadTestSettings(settle_seconds=60)).note
    svc, _, _ = _loadtest(tmp_path, never_starts=True)
    assert "no arrancó" in svc.run("P", [], settings=LoadTestSettings(start_timeout=30)).note


def test_baseline_errors_are_discarded_and_cached(tmp_path):
    svc, _, _ = _loadtest(tmp_path, log="[Error  : Unity Log] base game error\n[Message:   BepInEx] Chainloader startup complete\n")
    base = svc.baseline_errors("P")
    assert base == {"base game error"}
    assert svc.cache.get("baseline:build-1") == {"messages": ["base game error"]}

    svc2, _, _ = _loadtest(tmp_path)
    svc2.cache = svc.cache
    r = svc2.run_vs_baseline("P", ["A-Mod"], LoadTestSettings(settle_seconds=10))
    assert r.errors == ["[Error:Mod] x1 mod error"] and "descartados" in r.note
