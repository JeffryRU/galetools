"""In-memory implementations of the ports, used by the application tests."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from galetools.domain.errors import GaleToolsError
from galetools.domain.models import InstalledMod, PackageInfo, PackageRef


def make_zip(path: Path, files: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    path.write_bytes(buf.getvalue())
    return path


class FakeProfiles:
    def __init__(self, mods: dict[str, list[InstalledMod]], files: dict[str, set[str]] | None = None,
                 log: str | None = None, tmp: Path | None = None):
        self.mods = mods
        self.files = files or {}           # mod full_name -> relative paths present
        self.log = log
        self.tmp = tmp or Path(".")
        self.written: list[tuple[str, str, str]] = []
        self.texts: dict[Path, str] = {}

    def list_profiles(self):
        return sorted(self.mods)

    def installed_mods(self, profile):
        if profile not in self.mods:
            raise GaleToolsError("no existe")
        return self.mods[profile]

    def read_log(self, profile):
        return self.log

    def file_exists(self, mod, relative):
        return relative in self.files.get(mod.full_name, set())

    def write_mod_file(self, mod, kind, relative, data):
        self.written.append((mod.full_name, kind, relative))
        return True

    def build_test_profile(self, profile, mods, name):
        self.last_test = (name, [m.full_name for m in mods])
        return self.tmp / name

    def read_text(self, path):
        return self.texts.get(path)


class FakeRegistry:
    def __init__(self, packages: list[PackageInfo], zips: dict[str, Path] | None = None):
        self.packages = packages
        self.zips = zips or {}

    def info(self, ref):
        for p in self.packages:
            if p.ref.full_name.lower() == ref.full_name.lower():
                return p
        raise GaleToolsError("no encontrado")

    def all_packages(self):
        return self.packages

    def download(self, ref):
        return self.zips[str(ref)]


class FakeManager:
    def __init__(self):
        self.calls: list[tuple] = []

    def is_running(self):
        return True

    def select_profile(self, profile):
        self.calls.append(("select", profile))

    def install_package(self, ref):
        self.calls.append(("install", str(ref)))

    def install_local(self, path, profile):
        self.calls.append(("local", path.name, profile))

    def launch(self, profile, vanilla):
        self.calls.append(("launch", profile, vanilla))


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.on_sleep = None

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self.on_sleep:
            self.on_sleep(self.t)


class FakeGame:
    def __init__(self):
        self.pids: set[int] = set()
        self.killed: set[int] = set()
        self.started_with: Path | None = None

    def game_dir(self):
        return Path("game")

    def build_id(self):
        return "build-1"

    def running_pids(self):
        return set(self.pids)

    def start_with_profile(self, profile_dir):
        self.started_with = profile_dir

    def kill(self, pids):
        self.killed |= pids
        self.pids -= pids


class MemoryCache:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.data[key] = value


class FakeDecompiler:
    def __init__(self, sources: dict[str, str]):
        self.sources = sources  # dll stem -> C# source

    def is_managed(self, path):
        if path.suffix == ".dll":
            return path.stem in self.sources
        return None

    def decompile(self, dll, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "Plugin.cs").write_text(self.sources[dll.stem], encoding="utf-8")
        return None


class FakeAntivirus:
    def __init__(self, result="Scanning X found no threats."):
        self.result = result

    def scan(self, path):
        return self.result


def mod(name, version="1.0.0", deps=(), enabled=True, local=False, plugin_code=True):
    return InstalledMod(name, version, enabled, [Path("plugins") / name], list(deps), local, plugin_code)


def info(full_name, version="1.0.0", description="", downloads=0, deprecated=False):
    owner, name = full_name.split("-", 1)
    return PackageInfo(PackageRef(owner, name), version, description, [], downloads, "2026-11-01", deprecated)
