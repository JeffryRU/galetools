"""Use case: security scan of a Thunderstore package (download only, never runs it)."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from ..domain import scanrules
from ..domain.models import PackageRef, ScanReport
from ..ports import Decompiler, MalwareScanner, PackageRegistry
from .catalog import CatalogService


class ScanService:
    def __init__(self, catalog: CatalogService, registry: PackageRegistry, decompiler: Decompiler, malware: MalwareScanner):
        self.catalog = catalog
        self.registry = registry
        self.decompiler = decompiler
        self.malware = malware

    def scan(self, ref: PackageRef, run_malware_scan: bool = True) -> ScanReport:
        ref, info = self.catalog.resolve(ref)
        report = ScanReport(str(ref), categories=list(info.categories))
        zip_path = self.registry.download(ref)
        extracted = _extract(zip_path, zip_path.parent / "extracted")
        sources = zip_path.parent / "source"
        if sources.exists():
            shutil.rmtree(sources)

        for f in sorted(p for p in extracted.rglob("*") if p.is_file()):
            rel = str(f.relative_to(extracted))
            report.files.append(rel)
            kind = self.decompiler.is_managed(f)
            if kind is True:
                report.managed.append(rel)
                error = self.decompiler.decompile(f, sources / f.stem)
                if error:
                    report.decompile_errors.append(f"{rel}: {error}")
            elif kind is False or f.suffix.lower() in (".exe", ".so", ".dylib"):
                report.native.append(rel)

        for cs in sources.rglob("*.cs") if sources.exists() else []:
            text = cs.read_text(encoding="utf-8", errors="replace")
            report.lines_of_code += text.count("\n") + 1
            for label, hit in scanrules.find_hits(str(cs.relative_to(sources)), text):
                report.hits.setdefault(label, []).append(hit)

        if run_malware_scan:
            report.malware_scan = self.malware.scan(extracted)
        return report


def _extract(zip_path: Path, target: Path) -> Path:
    """Extracts into an empty folder, refusing entries that would escape it (zip-slip)."""
    if target.exists():
        shutil.rmtree(target)
    root = target.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            name = member.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            dest = (target / name).resolve()
            if root not in dest.parents:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(member))
    return target
