"""MCP server (stdio) exposing the same use cases as galectl.

Run: galetools-mcp   or   python -m galetools.entrypoints.mcp_server
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

try:  # MCP Python SDK v2
    from mcp.server import MCPServer as _Server
except ImportError:  # v1
    from mcp.server.fastmcp import FastMCP as _Server

from ..application.loadtest import LoadTestSettings
from ..container import build_app
from ..domain.errors import GaleToolsError
from ..domain.models import PackageRef
from . import presenters as view

app = build_app()
mcp = _Server("gale-ror2")
_DEFAULT = app.settings.default_profile


def _safe(fn: Callable[[], str]) -> str:
    try:
        return fn()
    except GaleToolsError as e:
        return "Error: " + str(e)


def _p(profile: str) -> str:
    return profile or _DEFAULT


@mcp.tool()
def gale_status() -> str:
    """Whether Gale and Risk of Rain 2 are running, the game folder, and the Gale profiles."""
    return _safe(lambda: view.status(app.profiles.status()))


@mcp.tool()
def list_mods(profile: str = "") -> str:
    """Lists the mods of a Gale profile (default profile if empty) with version and enabled state."""
    return _safe(lambda: view.mods(_p(profile), app.profiles.mods(_p(profile))))


@mcp.tool()
def search_mods(query: str, limit: int = 15) -> str:
    """Searches Risk of Rain 2 mods on Thunderstore by name and description, most downloaded first."""
    return _safe(lambda: view.search(query, *app.catalog.search(query, limit)))


@mcp.tool()
def mod_info(name: str, profile: str = "") -> str:
    """Folders, version and dependencies of one installed mod (partial names allowed)."""
    return _safe(lambda: view.mod_info(app.profiles.find(_p(profile), name)))


@mcp.tool()
def scan_package(package: str, antivirus: bool = True) -> str:
    """Security-scans a Thunderstore package (Owner-Name or Owner-Name-1.2.3): decompiles it, flags risky
    APIs and native code, and runs Windows Defender. Only downloads; never runs the mod."""
    return _safe(lambda: view.scan(app.scanner.scan(PackageRef.parse(package), run_malware_scan=antivirus)))


@mcp.tool()
def install_mod(package: str, profile: str = "", scan_first: bool = True) -> str:
    """Installs a Thunderstore mod (with dependencies) into a Gale profile through Gale itself.
    Scans it first by default and refuses if the antivirus flags it."""
    return _safe(lambda: view.install(app.installer.install(PackageRef.parse(package), _p(profile), scan_first)))


@mcp.tool()
def install_local_mod(path: str, profile: str = "") -> str:
    """Imports a local Thunderstore-style .zip into a Gale profile through Gale."""
    return _safe(lambda: "Enviado a Gale: importar " + app.installer.install_local(Path(path), _p(profile)).name)


@mcp.tool()
def verify_profile(profile: str = "", fix: bool = False, only: str = "") -> str:
    """Compares every installed mod with its official package and lists missing files.
    fix=True restores them from the official package."""
    return _safe(lambda: view.verify(app.verifier.verify_profile(_p(profile), fix, only or None)))


@mcp.tool()
def read_game_log(profile: str = "") -> str:
    """Summarises the profile's last BepInEx log: loaded plugins, grouped errors, enabled mods that did not load."""
    return _safe(lambda: view.diagnosis(app.diagnostics.diagnose(_p(profile))))


@mcp.tool()
def launch_game(profile: str = "", vanilla: bool = False) -> str:
    """Starts Risk of Rain 2 through Gale with a profile (or without mods if vanilla=True)."""
    def go() -> str:
        app.installer.launch(_p(profile), vanilla)
        return "Lanzando Risk of Rain 2"
    return _safe(go)


@mcp.tool()
def test_mod_load(mods: list[str], profile: str = "", settle_seconds: int = 45) -> str:
    """Starts the game with ONLY these mods (+ dependencies + core libraries) from a temporary copy of the
    profile, waits for loading, closes the game and reports errors not present in the base game.
    Refuses if the game is already open. Empty list = only core libraries."""
    return _safe(lambda: view.load_test(app.loadtests.run_vs_baseline(_p(profile), mods, LoadTestSettings(settle_seconds))))


@mcp.tool()
def test_each_mod(profile: str = "", settle_seconds: int = 30) -> str:
    """Loads every enabled mod on its own and reports which ones log errors. ~1 minute per mod;
    opens and closes the game repeatedly."""
    return _safe(lambda: view.load_tests(app.loadtests.test_each(_p(profile), LoadTestSettings(settle_seconds))))


@mcp.tool()
def bisect_error(error_text: str, profile: str = "", settle_seconds: int = 45) -> str:
    """Binary-searches which single mod makes `error_text` appear in the log (opens/closes the game several times)."""
    return _safe(lambda: view.bisect(*app.loadtests.bisect(_p(profile), error_text, LoadTestSettings(settle_seconds))))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
