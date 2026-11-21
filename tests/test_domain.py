import pytest

from galetools.domain import layout, scanrules
from galetools.domain.deps import dependency_closure, candidates_for_testing
from galetools.domain.errors import GaleToolsError
from galetools.domain.logparse import parse_log
from galetools.domain.models import PackageRef, ScanReport
from tests.fakes import mod


class TestPackageRef:
    def test_dash_forms(self):
        assert PackageRef.parse("KingEnderBrine-ProperSave") == PackageRef("KingEnderBrine", "ProperSave")
        assert PackageRef.parse("Rune580-Risk_Of_Options-2.8.6") == PackageRef("Rune580", "Risk_Of_Options", "2.8.6")

    def test_slash_form(self):
        assert PackageRef.parse("SDM/ROR_O/1.2.0") == PackageRef("SDM", "ROR_O", "1.2.0")

    def test_names_with_dashes_keep_version(self):
        assert PackageRef.parse("Zerik_MiniMapMod-MiniMapMod_Command_Lockbox_Fix-4.0.2").version == "4.0.2"

    def test_invalid(self):
        with pytest.raises(GaleToolsError):
            PackageRef.parse("nodash")


LOG = """\
[Message:   BepInEx] BepInEx 5.4.21.0 - Risk of Rain 2
[Info   :   BepInEx] TS Manifest: KingEnderBrine-ProperSave-3.1.3
[Info   :   BepInEx] Loading [Proper Save 3.1.3]
[Info   :   BepInEx] TS Manifest: |-VanillaPlusPerf-1.1.0
[Warning:     R2API] This version of R2API was built for build id "1.4.1", you are running "1.5.0".
[Error  : Unity Log] UnityEngine.AddressableAssets.InvalidKeyException: boom
[Error  : Unity Log] GenericPool: ReleasePools called on non-empty pool
[Error  : Unity Log] GenericPool: ReleasePools called on non-empty pool
[Warning: Unity Log] The prefab 'X' has multiple NetworkIdentity components.
[Error  : Unity Log] Failed to confine the cursor - ClipCursor failed: Acceso denegado.
[Message:   BepInEx] Chainloader startup complete
"""


class TestLogParse:
    def test_summary(self):
        s = parse_log(LOG)
        assert s.chainloader_done
        assert s.loaded == {"Proper Save": "3.1.3"}
        assert s.manifests == {"KingEnderBrine-ProperSave": "3.1.3"}  # local mods ("|-Name") are not Thunderstore names
        assert "1.4.1" in s.game_version_warning
        assert s.errors[("Error", "Unity Log", "GenericPool: ReleasePools called on non-empty pool")] == 2
        assert len(s.exceptions) == 1

    def test_noise_is_ignored(self):
        msgs = {m for (_, _, m) in parse_log(LOG).errors}
        assert not any("NetworkIdentity" in m or "ClipCursor" in m for m in msgs)


class TestLayout:
    def test_candidates_cover_gale_flattening(self):
        assert "ProperSave/Language/en/tokens.json" in layout.candidate_paths("plugins/ProperSave/Language/en/tokens.json")
        assert "StopStealingMyMouse.dll" in layout.candidate_paths("StopStealingMyMouse/StopStealingMyMouse.dll")
        assert "X/x.dll" in layout.candidate_paths("BepInEx\\patchers\\X\\x.dll")

    def test_should_check(self):
        assert layout.should_check("plugins/Mod/Mod.dll")
        assert not layout.should_check("README.md")
        assert not layout.should_check("plugins/Mod/Mod.pdb")
        assert not layout.should_check("config/mod.cfg")

    def test_restore_target(self):
        assert layout.restore_target("BepInEx/patchers/P/p.dll") == ("patchers", "P/p.dll")
        assert layout.restore_target("plugins/M/Lang/en.json") == ("plugins", "M/Lang/en.json")
        assert layout.restore_target("M.dll") == ("plugins", "M.dll")


class TestDeps:
    MODS = [
        mod("bbepis-BepInExPack"), mod("RiskofThunder-HookGenPatcher"),
        mod("Wolfo-WolfoQualityOfLife", deps=["Wolfo-WolfFixes-1.4.5"]),
        mod("Wolfo-WolfFixes", deps=["Goorakh-VFiX-1.1.3"]), mod("Goorakh-VFiX"),
        mod("Other-Mod"), mod("RiskofThunder-BepInEx_GUI"),
    ]

    def test_transitive_closure_plus_core(self):
        names = [m.full_name for m in dependency_closure(self.MODS, ["Wolfo-WolfoQualityOfLife"])]
        assert set(names) == {"bbepis-BepInExPack", "RiskofThunder-HookGenPatcher", "Wolfo-WolfoQualityOfLife",
                              "Wolfo-WolfFixes", "Goorakh-VFiX"}

    def test_console_window_never_in_tests(self):
        assert "RiskofThunder-BepInEx_GUI" not in [m.full_name for m in dependency_closure(self.MODS, ["RiskofThunder-BepInEx_GUI"])]

    def test_testable_skips_core_and_disabled(self):
        mods = self.MODS + [mod("Off-Mod", enabled=False)]
        names = [m.full_name for m in candidates_for_testing(mods)]
        assert "bbepis-BepInExPack" not in names and "Off-Mod" not in names and "Other-Mod" in names


class TestScanRules:
    def test_hits_and_verdict(self):
        src = "using System.Net;\nvar c = new HttpClient();\nFile.Delete(p);\n"
        hits = list(scanrules.find_hits("A.cs", src))
        labels = {label for label, _ in hits}
        assert labels == {"Red / descargas", "Borra o mueve archivos"}  # `using` lines are skipped
        r = ScanReport("x", hits={label: [h] for label, h in hits})
        assert scanrules.verdict(r).startswith("REVISAR")

    def test_clean_and_native(self):
        assert scanrules.verdict(ScanReport("x")) == "Sin señales de riesgo en el código"
        assert "nativo" in scanrules.verdict(ScanReport("x", native=["a.dll"]))

    def test_malware_detection(self):
        assert not scanrules.malware_detected("Scanning C:\\x found no threats.")
        assert not scanrules.malware_detected("no ejecutado")
        assert scanrules.malware_detected("Threat Trojan:Win32/X found")
        assert scanrules.verdict(ScanReport("x", malware_scan="Threat found")).startswith("PELIGRO")
