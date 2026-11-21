"""Use cases: automated load tests of mods in throw-away profiles.

A test builds a temporary profile with only the chosen mods (+ dependencies + core libraries), starts the
game pointing BepInEx at it, waits until loading finished and the log went quiet, closes the game and
reads the log. Safety: refuses to start if the game is already running, and only closes processes that
appeared after it started the game.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.deps import dependency_closure, candidates_for_testing
from ..domain.errors import GaleToolsError
from ..domain.logparse import parse_log
from ..domain.models import LoadTestResult
from ..ports import Clock, GameRunner, KeyValueCache, ProfileRepository


@dataclass
class LoadTestSettings:
    settle_seconds: int = 45
    start_timeout: int = 120
    timeout: int = 600
    poll_seconds: float = 3.0


class LoadTestService:
    def __init__(self, profiles: ProfileRepository, game: GameRunner, cache: KeyValueCache, clock: Clock):
        self.profiles = profiles
        self.game = game
        self.cache = cache
        self.clock = clock

    # ------------------------------------------------------------------ single run

    def run(self, profile: str, wanted: list[str], name: str = "prueba",
            settings: LoadTestSettings | None = None) -> LoadTestResult:
        s = settings or LoadTestSettings()
        if self.game.running_pids():
            raise GaleToolsError("Risk of Rain 2 ya está abierto. Ciérralo antes de lanzar una prueba.")

        mods = [m for m in self.profiles.installed_mods(profile) if m.enabled]
        known = {m.full_name.lower() for m in mods}
        unknown = [w for w in wanted if w.lower() not in known]
        if unknown:
            raise GaleToolsError("No están (o están desactivados) en el perfil: " + ", ".join(unknown))
        chosen = dependency_closure(mods, wanted)
        test_dir = self.profiles.build_test_profile(profile, chosen, name)
        log_path = test_dir / "BepInEx" / "LogOutput.log"
        result = LoadTestResult(name, [m.full_name for m in chosen])

        before = self.game.running_pids()
        start = self.clock.now()
        self.game.start_with_profile(test_dir)
        started: set[int] = set()
        last_len, last_change = -1, start
        try:
            while self.clock.now() - start < s.timeout:
                self.clock.sleep(s.poll_seconds)
                now = self.clock.now()
                if not started:
                    started = self.game.running_pids() - before
                    if not started and now - start > s.start_timeout:
                        result.note = "El juego no arrancó a tiempo (¿Steam cerrado o pidió confirmación?)."
                        break
                    continue
                if not (self.game.running_pids() & started):
                    result.note = "El juego se cerró solo durante la prueba (posible crash)."
                    break
                text = self.profiles.read_text(log_path) or ""
                if len(text) != last_len:
                    last_len, last_change = len(text), now
                if parse_log(text).chainloader_done and now - last_change > s.settle_seconds:
                    result.finished_loading = True
                    break
            else:
                result.note = f"Se agotó el tiempo ({s.timeout} s)."
        finally:
            if started:
                self.game.kill(started)

        result.seconds = self.clock.now() - start
        result.summary = parse_log(self.profiles.read_text(log_path) or "")
        result.finished_loading = result.finished_loading or (result.summary.chainloader_done and not result.note)
        result.errors = _errors(result, ignore=set())
        return result

    # ------------------------------------------------------------------ baseline

    def baseline_errors(self, profile: str, refresh: bool = False) -> set[str]:
        """Errors the game prints with only the core libraries, cached per game build."""
        key = "baseline:" + self.game.build_id()
        cached = None if refresh else self.cache.get(key)
        if cached is not None:
            return set(cached.get("messages", []))
        base = self.run(profile, [], name="base", settings=LoadTestSettings(settle_seconds=30))
        messages = sorted(base.summary.error_messages()) if base.summary else []
        # Only a clean, untouched baseline is trustworthy: if the game was closed early, crashed or someone
        # played in it, its errors are not "base game noise" and must not be cached (they would hide real errors).
        if base.finished_loading and not base.note:
            self.cache.put(key, {"messages": messages})
        else:
            raise GaleToolsError("La prueba base no terminó limpia (" + (base.note or "no llegó a cargar")
                                 + "). No se guardó; vuelve a lanzar la prueba sin tocar el juego mientras se ejecuta.")
        return set(messages)

    def run_vs_baseline(self, profile: str, wanted: list[str], settings: LoadTestSettings | None = None) -> LoadTestResult:
        ignore = self.baseline_errors(profile) if wanted else set()
        result = self.run(profile, wanted, settings=settings)
        if ignore and result.summary:
            dropped = len(result.summary.error_messages() & ignore)
            result.errors = _errors(result, ignore)
            if dropped:
                result.note = (result.note + " " if result.note else "") + f"{dropped} error(es) del juego base descartados."
        return result

    # ------------------------------------------------------------------ many runs

    def test_each(self, profile: str, settings: LoadTestSettings | None = None) -> list[LoadTestResult]:
        ignore = self.baseline_errors(profile)
        results = []
        for mod in candidates_for_testing(self.profiles.installed_mods(profile)):
            r = self.run(profile, [mod.full_name], name="cada-" + mod.full_name, settings=settings)
            r.errors = _errors(r, ignore)
            results.append(r)
        return results

    def bisect(self, profile: str, error_text: str, settings: LoadTestSettings | None = None) -> tuple[str | None, list[str]]:
        """Binary search for the single mod whose presence makes `error_text` appear. Returns (culprit, steps)."""
        pool = [m.full_name for m in candidates_for_testing(self.profiles.installed_mods(profile))]
        steps: list[str] = []
        needle = error_text.lower()

        def appears(group: list[str], label: str) -> bool:
            r = self.run(profile, group, name=f"bisect-{len(steps)}", settings=settings)
            hit = bool(r.summary) and any(needle in msg.lower() for (_, _, msg) in r.summary.errors)
            steps.append(f"{label}: {len(group)} mods -> {'aparece' if hit else 'no aparece'}")
            return hit

        if not pool or not appears(pool, "todos"):
            return None, steps
        while len(pool) > 1:
            half = pool[: len(pool) // 2]
            pool = half if appears(half, "mitad") else pool[len(pool) // 2:]
        return pool[0], steps


def _errors(result: LoadTestResult, ignore: set[str]) -> list[str]:
    if not result.summary:
        return []
    return [f"[{lvl}:{src}] x{n} {msg}" for (lvl, src, msg), n in result.summary.errors.most_common()
            if lvl in ("Error", "Fatal") and msg not in ignore]
