# galetools

CLI y servidor **MCP** para [Gale](https://github.com/Kesomannen/gale) y **Risk of Rain 2**:
instala, escanea, verifica y **prueba** mods desde la terminal o desde un asistente como Claude.

- Habla con Gale a través de **su propio CLI y sus enlaces `ror2mm://`**; nunca edita su base de datos.
- Las pruebas de carga usan **perfiles temporales**; tus perfiles y configuraciones no se tocan.
- Solo Windows (Gale + Steam + Windows Defender).

## Instalación

Requiere Python 3.10+ y, para `scan`, el SDK de .NET (`dotnet`).

```powershell
uv venv "$env:LOCALAPPDATA\galetools\venv"
uv pip install --python "$env:LOCALAPPDATA\galetools\venv\Scripts\python.exe" "galetools[mcp] @ git+https://github.com/JeffryRU/galetools"
```

> Usa una ruta corta para el entorno virtual: Windows limita las rutas a 260 caracteres.

Variables de entorno opcionales:

| Variable | Para qué |
|---|---|
| `GALETOOLS_PROFILE` | Perfil por defecto (si no, `Default`) |
| `GALE_EXE` | Ruta a `gale.exe` si no está en `Program Files\Gale` |
| `ROR2_DIR` | Carpeta del juego si no está en una biblioteca de Steam |
| `GALETOOLS_HOME` | Carpeta de caché, descargas y perfiles de prueba (por defecto `%LOCALAPPDATA%\galetools`) |

## CLI: `galectl`

```text
galectl status                       estado de Gale, del juego y perfiles
galectl mods                         mods del perfil (cambia el perfil con -p "Nombre")
galectl search command pause         busca en Thunderstore (más descargados primero)
galectl info LookingGlass            carpetas, versión y dependencias de un mod
galectl scan Autor-Mod[-1.2.3]       escaneo de seguridad: decompila (ILSpy), busca APIs de riesgo,
                                     detecta código nativo y pasa Windows Defender
galectl install Autor-Mod            escanea y, si el antivirus no detecta nada, instala con Gale
galectl install-local mod.zip        importa un zip local en Gale
galectl verify [--fix]               compara cada mod con su paquete oficial; --fix restaura lo que falte
galectl log                          resumen del último LogOutput.log: errores agrupados y mods que no cargaron
galectl launch [--vanilla]           lanza el juego con el perfil
galectl test Mod1 Mod2 ...           lanza el juego SOLO con esos mods (+dependencias), espera a que cargue,
                                     lo cierra y reporta los errores que no salen en el juego base
galectl test-each                    prueba cada mod por separado
galectl bisect "texto del error"     búsqueda binaria del mod que provoca un error
```

Las pruebas **no empiezan si Risk of Rain 2 ya está abierto** y solo cierran el proceso que ellas abrieron.

## Servidor MCP

```powershell
claude mcp add --scope user gale-ror2 -e GALETOOLS_PROFILE="Default" -- "$env:LOCALAPPDATA\galetools\venv\Scripts\galetools-mcp.exe"
```

Herramientas: `gale_status`, `list_mods`, `search_mods`, `mod_info`, `scan_package`, `install_mod`,
`install_local_mod`, `verify_profile`, `read_game_log`, `launch_game`, `test_mod_load`, `test_each_mod`,
`bisect_error`.

## Arquitectura

Puertos y adaptadores (hexagonal), en versión ligera:

```text
galetools/
├── domain/          Reglas puras, sin E/S: modelos, parser del log, reglas de seguridad,
│                    estructura de carpetas de Gale, resolución de dependencias
├── ports.py         Interfaces (Protocol) que la aplicación necesita del exterior
├── application/     Casos de uso: catálogo, escaneo, instalación, verificación,
│                    diagnóstico y pruebas de carga. Solo dependen de domain + ports
├── adapters/        Implementaciones reales: Gale (CLI y enlaces), Thunderstore (HTTP),
│                    perfiles en disco, Steam/juego, ILSpy, Windows Defender, caché JSON
├── entrypoints/     CLI (argparse) y servidor MCP: traducen entrada/salida, sin lógica
├── container.py     Raíz de composición: el único sitio que conecta puertos con adaptadores
└── config.py        Configuración desde variables de entorno
```

Las dependencias apuntan hacia dentro: `entrypoints → application → domain`, y `adapters` implementan
`ports`. Por eso los casos de uso se prueban con adaptadores falsos (`tests/fakes.py`), incluida una prueba
de carga completa con un reloj simulado, sin lanzar el juego.

```powershell
uv pip install --python <venv>\Scripts\python.exe -e ".[mcp,dev]"
<venv>\Scripts\python.exe -m pytest
```

## Licencia

MIT. No incluye código de Gale (GPL-3.0); solo usa su CLI y sus enlaces públicos.
