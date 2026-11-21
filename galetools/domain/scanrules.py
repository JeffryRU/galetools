"""Security heuristics for decompiled mod source. Pure functions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .models import ScanReport


@dataclass(frozen=True)
class Rule:
    label: str
    pattern: re.Pattern
    severity: str  # "alta" needs a close look, "media" is often legitimate


RULES = [
    Rule("Red / descargas", re.compile(r"System\.Net\.|WebClient|HttpClient|WebRequest|UnityWebRequest|TcpClient|UdpClient|\bSocket\b|Dns\."), "alta"),
    Rule("URLs en el código", re.compile(r"https?://[^\s\"']+"), "media"),
    Rule("Ejecuta programas", re.compile(r"Process\.Start|ProcessStartInfo|cmd\.exe|powershell"), "alta"),
    Rule("Carga código dinámico", re.compile(r"Assembly\.Load|LoadFrom\(|LoadFile\(|AppDomain\.CreateDomain|CSharpCodeProvider"), "alta"),
    Rule("Código nativo (P/Invoke)", re.compile(r"DllImport|GetDelegateForFunctionPointer|VirtualAlloc|LoadLibrary"), "media"),
    Rule("Registro de Windows", re.compile(r"Microsoft\.Win32|Registry\.(CurrentUser|LocalMachine|SetValue|GetValue)"), "alta"),
    Rule("Datos sensibles", re.compile(r"(?i)discord.{0,20}(token|webhook)|password|cookie|Login Data|Local State|wallet|SteamFriends|SteamUser\."), "alta"),
    Rule("Portapapeles", re.compile(r"Clipboard|systemCopyBuffer"), "media"),
    Rule("Base64 / cifrado", re.compile(r"FromBase64String|RijndaelManaged|AesManaged|Aes\.Create"), "media"),
    Rule("Borra o mueve archivos", re.compile(r"File\.Delete|Directory\.Delete|File\.Move"), "media"),
    Rule("Rutas fuera del juego", re.compile(r"SpecialFolder\.|GetFolderPath|AppData|Environment\.GetEnvironmentVariable"), "media"),
]
_SEVERITY = {r.label: r.severity for r in RULES}


def find_hits(file_label: str, source: str) -> Iterable[tuple[str, str]]:
    """Yields (rule label, 'file:line: code') for every risky line of one source file."""
    for i, line in enumerate(source.splitlines(), 1):
        if line.lstrip().startswith("using "):
            continue
        for rule in RULES:
            if rule.pattern.search(line):
                yield rule.label, f"{file_label}:{i}: {line.strip()[:160]}"


def malware_detected(scan_output: str) -> bool:
    text = scan_output.lower()
    if "no threats" in text or "no se encontraron amenazas" in text or "no ejecutado" in text or "no disponible" in text:
        return False
    return "threat" in text or "amenaza" in text


def verdict(report: ScanReport) -> str:
    if malware_detected(report.malware_scan):
        return "PELIGRO: el antivirus detectó una amenaza"
    high = [label for label in report.hits if _SEVERITY.get(label) == "alta"]
    if report.native:
        return "REVISAR: incluye código nativo que no se puede leer" + (
            f" + coincidencias de riesgo alto ({', '.join(high)})" if high else "")
    if high:
        return "REVISAR: hay coincidencias de riesgo alto: " + ", ".join(high)
    return "Sin señales de riesgo en el código"
