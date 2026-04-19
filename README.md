# Keyd Remapper

**Open-source desktop application to detect keyboards, search firmware, and remap keys using keyd on Linux.**

**Aplicación de escritorio de código abierto para detectar teclados, buscar firmware y remapear teclas usando keyd en Linux.**

---

## Features / Características

- **Smart device detection** — Distinguishes real keyboards from mice, power buttons, speakers, virtual devices, etc. / Detección inteligente que distingue teclados reales de ratones, botones de power, altavoces, dispositivos virtuales, etc.
- **Per-device configuration** — Create separate keyd `.conf` files for each keyboard / Configuración independiente por dispositivo con archivos `.conf` separados.
- **Firmware search** — Searches QMK Configurator, VIAL, GitHub, and generic firmware databases / Búsqueda en QMK Configurator, VIAL, GitHub y bases de datos genéricas.
- **Live monitor** — Real-time keyd event stream with auto-reconnect / Monitor de eventos keyd en tiempo real con reconexión automática.
- **keyd management** — Install, activate, and reload keyd directly from the UI / Gestión completa de keyd desde la interfaz.
- Clean web-based UI served by a local FastAPI backend / Interfaz web limpia servida por un backend FastAPI local.

---

## Download / Descarga

The easiest way to use Keyd Remapper is downloading the latest **AppImage** (portable, no installation required):

```bash
wget https://github.com/Pinedux/keyd-remapper/releases/download/v1.0.1/keyd-remapper-x86_64.AppImage
chmod +x keyd-remapper-x86_64.AppImage
./keyd-remapper-x86_64.AppImage
```

> The AppImage includes Python + backend + frontend bundled with PyInstaller, so it works on any modern x86_64 Linux distro without requiring Python or dependencies installed.

---

## Installation / Instalación

### Prerequisites / Requisitos previos

- Linux with `keyd` installed / Linux con `keyd` instalado
- Python 3 and a virtual environment (`.venv`) / Python 3 y un entorno virtual (`.venv`)
- Rust toolchain / Cadena de herramientas de Rust
- Node.js (for Tauri CLI) / Node.js (para el CLI de Tauri)

### Clone / Clonar

```bash
git clone https://github.com/Pinedux/keyd-remapper.git
cd keyd-remapper
```

### Run in development mode / Ejecutar en modo desarrollo

```bash
# Install Node dependencies
npm install

# Run the Tauri development build
npx tauri dev
```

Alternatively, you can run the Python backend directly without the desktop shell:

```bash
source .venv/bin/activate
KEYD_PORT=8474 python backend/main.py
# Then open http://127.0.0.1:8474 in your browser
```

---

## Quick Start (without building Tauri) / Inicio rápido (sin compilar Tauri)

If you just want to run the app quickly using Python and a native webview:

```bash
# Ensure the virtual environment is set up and dependencies are installed
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pip install pywebview

# Launch the desktop window
python3 launch.py
```

---

## Build / Compilación

### Tauri v2 (full desktop shell)

```bash
# Install dependencies
npm install

# Build the Tauri application for production
npx tauri build
```

Built packages (`.deb`, `.rpm`) will be available in `src-tauri/target/release/bundle/`.

### pywebview (lightweight alternative)

```bash
source .venv/bin/activate
pip install pywebview
python3 launch.py
```

### AppImage (standalone)

```bash
source .venv/bin/activate
pip install pyinstaller
python -m PyInstaller \
  --name keyd-remapper \
  --onefile \
  --add-data "backend:backend" \
  --add-data "frontend:frontend" \
  pyinstaller_entry.py

# Then package with appimagetool
mkdir -p AppDir/usr/bin
cp dist/keyd-remapper AppDir/usr/bin/
# ... create .desktop and AppRun ...
appimagetool AppDir/ keyd-remapper-x86_64.AppImage
```

---

## License / Licencia

This project is licensed under the **GNU General Public License v3.0**.

Este proyecto está licenciado bajo la **Licencia Pública General de GNU v3.0**.

---

## Original Repository / Repositorio Original

**Original repository:** https://github.com/Pinedux/keyd-remapper

Forks and derivative works must reference the original repository and comply with the GPL-3.0 terms.

Los forks y trabajos derivados deben hacer referencia al repositorio original y cumplir con los términos de la GPL-3.0.
