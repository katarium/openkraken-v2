<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=220&section=header&text=OpenKraken%20CLI&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Un%20agente%20de%20código%20con%20permisos%2C%20directo%20en%20tu%20terminal&descAlignY=55&descSize=18" width="100%" />

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=1000&color=F97316&center=true&vCenter=true&width=600&lines=Chateá+con+cualquier+modelo+de+GitHub+Models;Leé%2C+escribí+y+buscá+archivos+con+un+click;Vos+decidís%3A+allow+o+deny;Terminal+bonita%2C+cero+drama." alt="Typing SVG" />

<br/>

![Python](https://img.shields.io/badge/python-3.10%2B-orange?style=for-the-badge&logo=python&logoColor=white)
![Rich](https://img.shields.io/badge/UI-rich-orange?style=for-the-badge&logo=windowsterminal&logoColor=white)
![GitHub Models](https://img.shields.io/badge/backend-GitHub%20Models-blue?style=for-the-badge&logo=github&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=for-the-badge)
![Status](https://img.shields.io/badge/status-en%20desarrollo-yellow?style=for-the-badge)

</div>

---

## 🟧 ¿Qué es OpenKraken?

**OpenKraken** es un agente de línea de comandos con una TUI estilo `rich`, que se conecta a
[GitHub Models](https://github.com/marketplace/models) y puede leer, escribir, listar y buscar
archivos, además de ejecutar comandos de terminal — **todo bajo un sistema de permisos** que vos
controlás: *allow once*, *allow always*, *deny once* o *deny always*.

<div align="center">

```
╭──────────────────────────────────────── 🟧 OpenKraken CLI ────────────────────────────────────────╮
│                                                                                                     │
│                              __                   __                   _______  ____              │
│   ____ ______   ____   ____ |  | ______________  |  | __ ____   ____   \   _  \/_   |              │
│  /  _ \\____ \_/ __ \ /    \|  |/ /\_  __ \__  \ |  |/ // __ \ /    \  /  /_\  \|   |               │
│ (  <_> )  |_> >  ___/|   |  \    <  |  | \// __ \|    <\  ___/|   |  \ \  \_/   \   |               │
│  \____/|   __/ \___  >___|  /__|_ \ |__|  (____  /__|_ \\___  >___|  /  \_____  /___|               │
│        |__|        \/     \/     \/            \/     \/    \/     \/         \/                   │
│                                                                                                     │
╰────────────────────────────────────── Powered by GitHub Models ───────────────────────────────────╯
```

</div>

> 💡 Tip: grabá tu propia demo con [VHS](https://github.com/charmbracelet/vhs) o
> [asciinema](https://asciinema.org) y reemplazá el bloque de arriba por un GIF real —
> quedan géniales en README y no pesan nada.

---

## ✨ Features

| | |
|---|---|
| 🧠 **Multi-modelo** | Cualquier modelo del catálogo de GitHub Models (`openai/gpt-4o`, `deepseek/DeepSeek-R1`, `meta/Llama-3.3-70B-Instruct`, etc.) |
| 🛠️ **Tool calling nativo** | `read_file`, `write_file`, `list_directory`, `search_files`, `terminal` — con fallback automático a modo texto si el modelo no soporta function calling |
| 🔐 **Permisos granulares** | Cada herramienta pide confirmación la primera vez; podés recordar `allow`/`deny` por sesión y gestionarlos con `/perms` |
| 💾 **Historial persistente** | Toda la conversación se guarda en `history.json` entre sesiones |
| 🖥️ **TUI con `rich`** | Banner, barra de estado (modelo activo, carpeta, permisos guardados) y paneles de resultado |
| ♻️ **Reintentos automáticos** | Backoff exponencial ante `RateLimitError` |

---

## 📦 Instalación

```bash
git clone https://github.com/tu-usuario/openkraken.git
cd openkraken

python -m venv venv
source venv/bin/activate      # en Windows: venv\Scripts\activate

pip install openai rich
```

## 🚀 Uso

```bash
python openkraken.py
```

Te va a pedir:

1. **GitHub Token** (con acceso a GitHub Models)
2. **Modelo**, en formato `publisher/modelo` — ej: `openai/gpt-4o`, `deepseek/DeepSeek-R1`

Y listo, ya podés chatear:

```
> Leé el archivo config.json y decime si falta alguna clave
```

### Comandos disponibles dentro del chat

| Comando | Qué hace |
|---|---|
| `/perms` | Ver y editar los permisos guardados (`allow` / `deny` / `clear`) |
| `/reset` | Borra todos los permisos guardados |
| `/exit` o `/quit` | Guarda el historial y sale |

---

## 🔐 Sistema de permisos

Cada vez que el modelo quiere tocar el sistema de archivos o correr un comando, vas a ver algo así:

```
⚠  Permiso requerido: write_file
   Escribir archivo: cloner.py
   --- contenido ---
   import requests ...

  1) Allow once   2) Allow always   3) Deny once   4) Deny always
  » Elegí una opción (1-4, default 1):
```

- **Allow once / Deny once** → aplica sólo a esa acción puntual.
- **Allow always / Deny always** → se guarda en `permissions.json` y no te vuelve a preguntar por esa herramienta.
- Podés revisar o cambiar todo esto en cualquier momento con `/perms`, o resetear todo con `/reset`.

---

## 🗺️ Roadmap

- [ ] Modo "dry-run" para ver qué haría el agente sin ejecutar nada
- [ ] Permisos por ruta (no sólo por herramienta) — ej: `allow` solo dentro de `./src`
- [ ] Historial multi-sesión con nombres (`/new`, `/sessions`)
- [ ] Soporte de streaming combinado con function calling

---

## 🤝 Contribuir

Los PRs son bienvenidos. Si encontrás un bug o tenés una idea, abrí un issue primero para charlarlo.

## 📄 Licencia

MIT — usalo, rompelo, mejoralo.

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer" width="100%" />

</div>
