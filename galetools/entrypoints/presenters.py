"""Plain-text rendering of results, shared by the CLI and the MCP server."""
from __future__ import annotations

from ..application.catalog import Status
from ..application.diagnostics import Diagnosis
from ..application.installing import InstallOutcome
from ..domain import scanrules
from ..domain.models import InstalledMod, LoadTestResult, PackageInfo, ScanReport, VerifyResult


def status(s: Status) -> str:
    return "\n".join([
        f"Gale abierto: {'sí' if s.gale_running else 'no'}",
        f"Risk of Rain 2 abierto: {'sí' if s.game_running else 'no'}",
        f"Juego: {s.game_dir}",
        "Perfiles: " + (", ".join(s.profiles) or "(ninguno)"),
    ])


def mods(profile: str, items: list[InstalledMod]) -> str:
    on = sum(m.enabled for m in items)
    rows = [f"{'✓' if m.enabled else '✗'} {m.full_name} {m.version}" + (" (local)" if m.local else "") for m in items]
    return f"Perfil '{profile}': {len(items)} mods ({on} activos)\n" + "\n".join(rows)


def mod_info(m: InstalledMod, root_hint: str = "") -> str:
    folders = "\n".join(f"  {f}" for f in m.folders)
    deps = "\n".join("  " + d for d in m.dependencies) or "  (ninguna)"
    return f"{m.full_name} {m.version} ({'activo' if m.enabled else 'desactivado'})\nCarpetas:\n{folders}\nDependencias:\n{deps}"


def search(query: str, total: int, items: list[PackageInfo]) -> str:
    out = [f"{total} resultados para '{query}'" + (f" (mostrando {len(items)})" if total > len(items) else "")]
    for p in items:
        tags = ", ".join(c for c in p.categories if c in ("AI Generated", "Client-side", "Server-side"))
        out.append(f"- {p.ref.full_name} {p.latest_version} | {p.date_updated[:10]} | {p.downloads:,} descargas"
                   + (f" | {tags}" if tags else "") + f"\n    {p.description[:150]}")
    return "\n".join(out)


def scan(r: ScanReport, max_hits: int = 6) -> str:
    out = [f"== Escaneo de {r.package}",
           f"Archivos: {len(r.files)} | DLL .NET: {len(r.managed)} | nativas/exe: {len(r.native)} | líneas decompiladas: {r.lines_of_code}"]
    if r.categories:
        out.append("Etiquetas Thunderstore: " + ", ".join(r.categories))
    if r.native:
        out.append("Código nativo (no revisable): " + ", ".join(r.native))
    out += ["No se pudo decompilar: " + e for e in r.decompile_errors]
    for label, hits in r.hits.items():
        out.append(f"- {label}: {len(hits)} coincidencias")
        out += ["    " + h for h in hits[:max_hits]]
    out.append("Antivirus: " + r.malware_scan)
    out.append("Veredicto: " + scanrules.verdict(r))
    return "\n".join(out)


def install(o: InstallOutcome) -> str:
    text = (scan(o.scan) + "\n\n") if o.scan else ""
    if not o.installed:
        return text + "No se instaló por el resultado del escaneo."
    return text + (f"Enviado a Gale: instalar {o.ref}" + (f" en '{o.profile}'" if o.profile else "")
                   + ". Gale lo descarga con sus dependencias; si muestra una confirmación, acéptala en su ventana.")


def verify(results: list[VerifyResult]) -> str:
    lines = []
    for r in results:
        if r.skipped_reason:
            lines.append(f"  - {r.mod}: omitido ({r.skipped_reason})")
        if r.restored:
            lines.append(f"  * {r.mod} {r.version}: restaurados {len(r.restored)} archivos")
        if r.missing:
            lines.append(f"  ! {r.mod} {r.version}: FALTAN {len(r.missing)}: " + ", ".join(r.missing[:6])
                         + (" ..." if len(r.missing) > 6 else ""))
    complete = sum(1 for r in results if r.ok and not r.restored)
    broken = sum(1 for r in results if r.missing)
    return "\n".join([f"{len(results)} mods revisados: {complete} completos, {broken} con archivos faltantes.", *lines])


def diagnosis(d: Diagnosis, max_items: int = 25) -> str:
    s = d.summary
    if not d.log_found:
        return "Este perfil todavía no tiene LogOutput.log (no se ha lanzado el juego con él)."
    real = [(k, v) for k, v in s.errors.most_common() if k[0] in ("Error", "Fatal")]
    warnings = sum(v for k, v in s.errors.items() if k[0] == "Warning")
    out = [f"Plugins cargados: {len(s.loaded)} | carga de mods completa: {'sí' if s.chainloader_done else 'NO'}"]
    if s.game_version_warning:
        out.append("Aviso: " + s.game_version_warning)
    out.append(f"Errores: {sum(v for _, v in real)} ({len(real)} distintos) | Advertencias: {warnings}")
    out += [f"  [{lvl}:{src}] x{n} {msg[:180]}" for (lvl, src, msg), n in real[:max_items]]
    if d.not_loaded:
        out.append("Mods activos que NO aparecen cargados en el log: " + ", ".join(d.not_loaded))
    return "\n".join(out)


def load_test(r: LoadTestResult) -> str:
    lines = [f"[{'OK' if r.ok else 'FALLO'}] {r.name} ({len(r.mods)} mods, {r.seconds:.0f} s)"]
    if r.note:
        lines.append("  " + r.note)
    lines += ["  " + e[:220] for e in r.errors[:15]]
    return "\n".join(lines)


def load_tests(results: list[LoadTestResult]) -> str:
    bad = [r for r in results if not r.ok]
    return f"{len(results)} mods probados por separado: {len(bad)} con problemas.\n" + "\n".join(load_test(r) for r in results)


def bisect(culprit: str | None, steps: list[str]) -> str:
    head = (f"Mod culpable (junto con sus dependencias): {culprit}" if culprit
            else "El error no aparece con todos los mods; no se puede aislar.")
    return head + "\n" + "\n".join(steps)
