"""galectl - command line interface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..application.loadtest import LoadTestSettings
from ..container import App, build_app
from ..domain.errors import GaleToolsError
from ..domain.models import PackageRef
from . import presenters as view


def _parser(default_profile: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="galectl", description="Herramientas para Gale y Risk of Rain 2.")
    p.add_argument("-p", "--profile", default=default_profile,
                   help=f"perfil de Gale (por defecto: {default_profile}; cámbialo con GALETOOLS_PROFILE)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="estado de Gale, del juego y perfiles")
    sub.add_parser("mods", help="mods del perfil")
    s = sub.add_parser("search", help="busca mods en Thunderstore")
    s.add_argument("query", nargs="+")
    s.add_argument("-n", "--limit", type=int, default=15)
    s = sub.add_parser("info", help="detalle de un mod instalado")
    s.add_argument("name")
    s = sub.add_parser("scan", help="escaneo de seguridad de un paquete (Autor-Nombre[-versión])")
    s.add_argument("package")
    s.add_argument("--no-defender", action="store_true")
    s = sub.add_parser("install", help="escanea e instala un mod de Thunderstore a través de Gale")
    s.add_argument("package")
    s.add_argument("--no-scan", action="store_true")
    s = sub.add_parser("install-local", help="importa un .zip local en Gale")
    s.add_argument("path")
    s = sub.add_parser("verify", help="comprueba que no falten archivos en los mods")
    s.add_argument("--fix", action="store_true", help="restaura desde el paquete oficial lo que falte")
    s.add_argument("--only")
    sub.add_parser("log", help="resumen del último LogOutput.log del perfil")
    s = sub.add_parser("launch", help="lanza el juego con el perfil a través de Gale")
    s.add_argument("--vanilla", action="store_true")
    for name, help_text in (("test", "lanza el juego solo con esos mods (+dependencias) y revisa el log"),
                            ("test-each", "prueba cada mod por separado (tarda bastante)"),
                            ("bisect", "busca qué mod provoca un error del log")):
        s = sub.add_parser(name, help=help_text)
        if name == "test":
            s.add_argument("mods", nargs="*")
        if name == "bisect":
            s.add_argument("error_text")
        s.add_argument("--settle", type=int, default=45, help="segundos sin actividad en el log antes de cerrar")
    return p


def run(app: App, argv: list[str] | None = None) -> str:
    a = _parser(app.settings.default_profile).parse_args(argv)
    profile = a.profile
    tests = LoadTestSettings(settle_seconds=getattr(a, "settle", 45))
    match a.cmd:
        case "status":
            return view.status(app.profiles.status())
        case "mods":
            return view.mods(profile, app.profiles.mods(profile))
        case "search":
            query = " ".join(a.query)
            return view.search(query, *app.catalog.search(query, a.limit))
        case "info":
            return view.mod_info(app.profiles.find(profile, a.name))
        case "scan":
            return view.scan(app.scanner.scan(PackageRef.parse(a.package), run_malware_scan=not a.no_defender))
        case "install":
            return view.install(app.installer.install(PackageRef.parse(a.package), profile, scan_first=not a.no_scan))
        case "install-local":
            path = app.installer.install_local(Path(a.path), profile)
            return f"Enviado a Gale: importar mod local {path.name} en '{profile}'"
        case "verify":
            return view.verify(app.verifier.verify_profile(profile, fix=a.fix, only=a.only))
        case "log":
            return view.diagnosis(app.diagnostics.diagnose(profile))
        case "launch":
            app.installer.launch(profile, a.vanilla)
            return "Lanzando Risk of Rain 2 " + ("sin mods" if a.vanilla else f"con el perfil '{profile}'")
        case "test":
            return view.load_test(app.loadtests.run_vs_baseline(profile, a.mods, tests))
        case "test-each":
            return view.load_tests(app.loadtests.test_each(profile, tests))
        case "bisect":
            return view.bisect(*app.loadtests.bisect(profile, a.error_text, tests))
    raise GaleToolsError(f"Comando desconocido: {a.cmd}")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    try:
        print(run(build_app(), argv))
        return 0
    except GaleToolsError as e:
        print("Error: " + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
