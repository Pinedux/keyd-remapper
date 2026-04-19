# Keyd Remapper

**Open-source desktop application to detect keyboards, search firmware, and remap keys using keyd on Linux.**

**Aplicación de escritorio de código abierto para detectar teclados, buscar firmware y remapear teclas usando keyd en Linux.**

---

## Features / Características

- Detect connected keyboards automatically / Detecta teclados conectados automáticamente
- Search and download keyboard firmware / Busca y descarga firmware de teclados
- Remap keys using [keyd](https://github.com/rvaiya/keyd) on Linux / Remapea teclas usando keyd en Linux
- Clean web-based UI served by a local FastAPI backend / Interfaz web limpia servida por un backend FastAPI local
- Cross-platform Tauri v2 desktop shell / Shell de escritorio multiplataforma con Tauri v2

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
cargo tauri dev
```

Alternatively, you can run the Python backend directly without the desktop shell:

```bash
source .venv/bin/activate
KEYD_PORT=8474 python backend/main.py
# Then open http://127.0.0.1:8474 in your browser
```

---

## Build / Compilación

```bash
# Install dependencies
npm install

# Build the Tauri application for production
cargo tauri build
```

Built packages (`.deb`, `.rpm`, `.AppImage`) will be available in `src-tauri/target/release/bundle/`.

---

## License / Licencia

This project is licensed under the **GNU General Public License v3.0**.

Este proyecto está licenciado bajo la **Licencia Pública General de GNU v3.0**.

---

## Original Repository / Repositorio Original

**Original repository:** https://github.com/Pinedux/keyd-remapper

Forks and derivative works must reference the original repository and comply with the GPL-3.0 terms.

Los forks y trabajos derivados deben hacer referencia al repositorio original y cumplir con los términos de la GPL-3.0.
