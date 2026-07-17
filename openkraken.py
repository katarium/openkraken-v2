import json
import os
import re
import subprocess
import time
from urllib.parse import quote

import requests
from openai import OpenAI, RateLimitError
from pypresence import Presence
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "brand": "bold orange1",
        "brand.dim": "orange1",
        "muted": "grey58",
        "accent": "bold khaki1",
        "ok": "bold spring_green3",
        "warn": "bold gold3",
        "err": "bold red3",
        "user": "bold deep_sky_blue1",
        "assistant": "bold orange1",
        "tool": "bold khaki1",
    }
)

console = Console(theme=THEME)

APP_NAME = "OpenKraken"
APP_VERSION = "v2"
IMG_MODEL_NAME = "OpenCarma v1"

TOOL_ICONS = {
    "read_file": "📄",
    "write_file": "📝",
    "list_directory": "📁",
    "search_files": "🔍",
    "terminal": "💻",
}

CLIENT_ID = "1508280695745810562"
discord_rpc = None
rpc_connected = False
start = int(time.time())


def _connect_rpc():
    global discord_rpc, rpc_connected
    try:
        discord_rpc = Presence(CLIENT_ID)
        discord_rpc.connect()
        rpc_connected = True
    except Exception:
        discord_rpc = None
        rpc_connected = False


def update_rpc(estado="Esperando comandos", detalle="OpenKraken CLI"):
    global discord_rpc, rpc_connected
    if not rpc_connected or discord_rpc is None:
        _connect_rpc()

    if not rpc_connected or discord_rpc is None:
        return

    try:
        discord_rpc.update(
            state=estado,
            details=detalle,
            start=start,
            large_image="logo",
            large_text=f"{APP_NAME} {APP_VERSION}",
            buttons=[
                {"label": "🌐 Web", "url": "https://openkraken.netlify.app/"},
                {
                    "label": "💻 GitHub",
                    "url": "https://github.com/katarium/openkraken-v2",
                },
            ],
        )
    except Exception:
        rpc_connected = False
        try:
            discord_rpc.close()
        except Exception:
            pass
        discord_rpc = None


def close_rpc():
    global discord_rpc, rpc_connected

    try:
        if discord_rpc:
            discord_rpc.close()
    except Exception:
        pass
    discord_rpc = None
    rpc_connected = False


GITHUB_TOKEN = ""
MODEL = ""
client = None

HISTORY_FILE = "history.json"
PERMISSIONS_FILE = "permissions.json"

PERMISSIONS = {}


def load_permissions():
    global PERMISSIONS
    if os.path.exists(PERMISSIONS_FILE):
        try:
            with open(PERMISSIONS_FILE, "r", encoding="utf-8") as f:
                PERMISSIONS = json.load(f)
        except Exception:
            PERMISSIONS = {}
    return PERMISSIONS


def save_permissions():
    with open(PERMISSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(PERMISSIONS, f, indent=2, ensure_ascii=False)


def check_permission(tool_name, preview):
    state = PERMISSIONS.get(tool_name)
    icon = TOOL_ICONS.get(tool_name, "🔧")

    if state == "allow":
        console.print(
            f"[muted]  {icon} permiso recordado → [ok]allow[/ok] · {tool_name}[/muted]"
        )
        return True
    if state == "deny":
        console.print(
            f"[muted]  {icon} permiso recordado → [err]deny[/err] · {tool_name}[/muted]"
        )
        return False

    console.print()
    console.print(
        Panel(
            Text(preview, style="white"),
            title=f"[warn]{icon}  Permiso requerido · {tool_name}[/warn]",
            title_align="left",
            border_style="gold3",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )

    options = Table.grid(padding=(0, 2))
    options.add_row(
        "[ok]1[/ok] Allow once",
        "[ok]2[/ok] Allow always",
        "[err]3[/err] Deny once",
        "[err]4[/err] Deny always",
    )
    console.print(Padding(options, (0, 2)))

    choice = console.input(
        "\n  [brand]› Elegí una opción (1-4, default 1): [/brand]"
    ).strip()
    console.print()

    if choice == "2":
        PERMISSIONS[tool_name] = "allow"
        save_permissions()
        return True
    if choice == "4":
        PERMISSIONS[tool_name] = "deny"
        save_permissions()
        return False
    if choice == "3":
        return False
    return True


def reset_permissions():
    global PERMISSIONS
    PERMISSIONS = {}
    if os.path.exists(PERMISSIONS_FILE):
        os.remove(PERMISSIONS_FILE)
    console.print("[ok]✓ Permisos reiniciados.[/ok]\n")


def setup():
    global GITHUB_TOKEN, MODEL, client

    console.print()
    console.print(Rule("[brand]Configuración inicial[/brand]", style="orange1"))
    console.print()
    GITHUB_TOKEN = console.input("  [brand]🔑 GitHub Token:[/brand] ").strip()
    console.print(
        "  [muted]Tip: en GitHub Models los IDs van como 'publisher/modelo', "
        "ej: openai/gpt-4o, deepseek/DeepSeek-R1, meta/Llama-3.3-70B-Instruct[/muted]"
    )
    MODEL = console.input("  [brand]🧠 Model (ej: openai/gpt-4o):[/brand] ").strip()

    client = OpenAI(
        api_key=GITHUB_TOKEN,
        base_url="https://models.github.ai/inference",
    )

    load_permissions()
    console.print()


def banner():
    art = Text(
        r"""
                             __                   __                   _______  ____
  ____ ______   ____   ____ |  | ______________  |  | __ ____   ____   \   _  \/_   |
 /  _ \\____ \_/ __ \ /    \|  |/ /\_  __ \__  \ |  |/ // __ \ /    \  /  /_\  \|   |
(  <_> )  |_> >  ___/|   |  \    <  |  | \// __ \|    <\  ___/|   |  \ \  \_/   \   |
 \____/|   __/ \___  >___|  /__|_ \ |__|  (____  /__|_ \\___  >___|  /  \_____  /___|
       |__|        \/     \/     \/            \/     \/    \/     \/         \/
""",
        style="brand",
    )

    subtitle = Text()
    subtitle.append("Powered by GitHub Models", style="brand.dim")
    subtitle.append("   ·   ", style="muted")
    subtitle.append(f"Imágenes por {IMG_MODEL_NAME}", style="accent")

    console.print(
        Panel(
            Group(Align.center(art), Align.center(subtitle)),
            title=f"🟧 {APP_NAME} CLI · {APP_VERSION}",
            border_style="orange1",
            box=box.DOUBLE,
            padding=(1, 2),
        )
    )


def status_bar():
    """Barra inferior estilo status bar: modelo, cwd, permisos y atajos."""
    cwd = os.path.basename(os.getcwd()) or os.getcwd()
    allow_count = sum(1 for v in PERMISSIONS.values() if v == "allow")
    deny_count = sum(1 for v in PERMISSIONS.values() if v == "deny")

    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right", ratio=1)
    grid.add_row(
        f"[brand]🧠 {MODEL or '—'}[/brand]  [muted]·[/muted]  [muted]📂 ~/{cwd}[/muted]",
        f"[ok]{allow_count} allow[/ok]  [err]{deny_count} deny[/err]",
    )

    console.print(Rule(style="grey35"))
    console.print(grid)
    console.print(
        "[muted]/help ayuda · /exit salir · /perms permisos · /reset borrar permisos · "
        "/image · /flux generar imágenes[/muted]\n"
    )


def help_panel():
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="brand")
    table.add_column("Comando", style="accent")
    table.add_column("Descripción", style="white")
    table.add_row("/help", "Muestra esta ayuda")
    table.add_row("/perms", "Gestiona permisos guardados")
    table.add_row("/reset", "Borra todos los permisos guardados")
    table.add_row("/image <prompt>", f"Genera una imagen con {IMG_MODEL_NAME}")
    table.add_row(
        "/flux <prompt>", f"Genera una imagen con {IMG_MODEL_NAME} (modo Flux)"
    )
    table.add_row("/exit, /quit", "Guarda el historial y sale")
    console.print(
        Panel(table, title="🟧 Ayuda", border_style="orange1", box=box.ROUNDED)
    )
    console.print()


def input_panel():
    console.print(
        Panel(
            '[muted]Escribí tu mensaje... ej: "lee config.json y arreglá el bug"[/muted]',
            border_style="grey35",
            title="[brand]› input[/brand]",
            title_align="left",
            box=box.ROUNDED,
        )
    )


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        {
            "role": "system",
            "content": f"""
        Eres {APP_NAME}, un asistente que puede interactuar con el sistema de archivos.

        Tenés disponibles herramientas (function calling): read_file, write_file,
        list_directory, search_files y terminal. Usalas directamente cuando el
        usuario pida leer, escribir, listar o buscar algo, o ejecutar un comando.

        Si en algún momento no tenés function calling disponible, respondé
        únicamente con este formato de JSON en tu mensaje:
        {{"tool":"read_file","args":{{"path":"archivo"}}}}
        {{"tool":"write_file","args":{{"path":"archivo","content":"..."}}}}
        {{"tool":"list_directory","args":{{"path":"."}}}}
        {{"tool":"search_files","args":{{"keyword":"texto","path":"."}}}}
        {{"tool":"terminal","args":{{"command":"ls"}}}}

        Toda herramienta que toque el sistema de archivos o ejecute comandos
        requiere permiso explícito del usuario (allow/deny), así que puede que
        una acción sea rechazada; en ese caso proponé una alternativa.

        NO digas que vas a hacer algo sin hacerlo: si podés usar una herramienta
        para resolver el pedido, usala en la misma respuesta en vez de anunciarla.
        """,
        }
    ]


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def read_file(path):
    if not check_permission("read_file", f"Leer archivo: {path}"):
        return "[DENIED] read_file"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR reading file]: {e}"


def write_file(path, content):
    preview = f"Escribir archivo: {path}\n\n--- contenido ---\n{content[:400]}"
    if not check_permission("write_file", preview):
        return "[DENIED] write_file"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] File written: {path}"
    except Exception as e:
        return f"[ERROR writing file]: {e}"


def list_directory(path="."):
    if not check_permission("list_directory", f"Listar directorio: {path}"):
        return "[DENIED] list_directory"
    try:
        items = os.listdir(path)
        return "\n".join(items)
    except Exception as e:
        return f"[ERROR listing directory]: {e}"


def search_files(keyword, path="."):
    if not check_permission("search_files", f"Buscar '{keyword}' dentro de: {path}"):
        return "[DENIED] search_files"
    results = []
    for root, dirs, files in os.walk(path):
        for file in files:
            try:
                full_path = os.path.join(root, file)
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    if keyword in f.read():
                        results.append(full_path)
            except Exception:
                continue
    return "\n".join(results) if results else "No matches found"


def run_terminal(command):
    if not check_permission("terminal", f"Ejecutar en terminal:\n$ {command}"):
        return "[DENIED] terminal"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = (result.stdout + "\n" + result.stderr).strip()
        return output
    except Exception as e:
        return f"[ERROR terminal]: {e}"


def run_tool(tool_name, args):
    if tool_name == "read_file":
        return read_file(args.get("path"))
    if tool_name == "write_file":
        return write_file(args.get("path"), args.get("content", ""))
    if tool_name == "list_directory":
        return list_directory(args.get("path", "."))
    if tool_name == "search_files":
        return search_files(args.get("keyword"), args.get("path", "."))
    if tool_name == "terminal":
        return run_terminal(args.get("command"))
    return "[ERROR] Unknown tool"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee y devuelve el contenido de un archivo de texto",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe (sobrescribe) contenido en un archivo",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"},
                    "content": {"type": "string", "description": "Contenido nuevo"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lista los archivos y carpetas dentro de un directorio",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Ruta del directorio (default '.')",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Busca un texto (keyword) dentro de todos los archivos de una carpeta",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Texto a buscar"},
                    "path": {
                        "type": "string",
                        "description": "Carpeta donde buscar (default '.')",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Ejecuta un comando de terminal/shell",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando a ejecutar"}
                },
                "required": ["command"],
            },
        },
    },
]

SUPPORTS_TOOLS = True


def _tools_unsupported_error(e):
    msg = str(e).lower()
    return "tool" in msg and (
        "not support" in msg or "unsupported" in msg or "invalid" in msg or "400" in msg
    )


def try_parse_tool(text):
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
        if "tool" in data and "args" in data:
            return data
    except Exception:
        return None
    return None


def chat_with_retry(*args, max_retries=5, **kwargs):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(*args, **kwargs)
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait = 2**attempt
            console.print(f"[warn]⏳ Rate limited. Esperando {wait}s...[/warn]")
            time.sleep(wait)


def print_tool_result(name, result):
    icon = TOOL_ICONS.get(name, "🔧")
    text = str(result)
    truncated = False
    if len(text) > 2000:
        text = text[:2000] + "\n…"
        truncated = True

    console.print(
        Panel(
            text if text.strip() else "[muted](sin salida)[/muted]",
            title=f"[tool]{icon} {name}[/tool]"
            + (" [muted](truncado)[/muted]" if truncated else ""),
            title_align="left",
            border_style="khaki1",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )


def print_assistant_message(text):
    if not text.strip():
        return
    console.print()
    console.print(
        Panel(
            Markdown(text),
            title=f"[assistant]🟧 {APP_NAME}[/assistant]",
            title_align="left",
            border_style="orange1",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def agent_loop(history, max_tool_steps=25):
    global SUPPORTS_TOOLS

    for _ in range(max_tool_steps):
        try:
            with console.status("[brand]💭 Pensando...[/brand]", spinner="dots"):
                if SUPPORTS_TOOLS:
                    response = chat_with_retry(
                        model=MODEL, messages=history, tools=TOOLS, tool_choice="auto"
                    )
                else:
                    response = chat_with_retry(model=MODEL, messages=history)
        except Exception as e:
            if SUPPORTS_TOOLS and _tools_unsupported_error(e):
                console.print(
                    "[warn]⚠ Este modelo no soporta function calling nativo. "
                    "Cambiando a modo texto (JSON en la respuesta).[/warn]"
                )
                SUPPORTS_TOOLS = False
                continue
            console.print(
                Panel(
                    f"[err]{e}[/err]\n\n"
                    "[muted]Revisá que el nombre del modelo sea válido. En GitHub Models "
                    "suelen ir con formato 'publisher/modelo', ej: openai/gpt-4o, "
                    "deepseek/DeepSeek-R1, meta/Llama-3.3-70B-Instruct.[/muted]",
                    title="✖ Error llamando al modelo",
                    border_style="red3",
                    box=box.ROUNDED,
                )
            )
            return

        message = response.choices[0].message

        if SUPPORTS_TOOLS and getattr(message, "tool_calls", None):
            if message.content:
                print_assistant_message(message.content)

            history.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )

            for tc in message.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}

                result = run_tool(name, args)
                print_tool_result(name, result)

                history.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
                )

            continue

        text = message.content or ""
        print_assistant_message(text)

        tool_call = None if SUPPORTS_TOOLS else try_parse_tool(text)

        if not tool_call:
            history.append({"role": "assistant", "content": text})
            return

        tool = tool_call["tool"]
        args = tool_call.get("args", {})
        result = run_tool(tool, args)
        print_tool_result(tool, result)

        history.append({"role": "assistant", "content": text})
        history.append(
            {"role": "user", "content": f"Tool result:\n{result}\nContinue."}
        )

    console.print(
        "[warn]⚠ Se alcanzó el límite de pasos de herramientas para este turno.[/warn]"
    )


def show_permissions_menu():
    if not PERMISSIONS:
        console.print("[muted]No hay permisos guardados todavía.[/muted]\n")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="brand")
    table.add_column("Herramienta", style="accent")
    table.add_column("Estado", justify="center")
    for k, v in PERMISSIONS.items():
        icon = TOOL_ICONS.get(k, "🔧")
        style = "ok" if v == "allow" else "err"
        table.add_row(f"{icon} {k}", f"[{style}]{v}[/{style}]")

    console.print(
        Panel(
            table,
            title="🟧 Permisos guardados",
            border_style="orange1",
            box=box.ROUNDED,
        )
    )

    tool = console.input(
        "\n[brand]› Nombre de herramienta a modificar (enter para salir): [/brand]"
    ).strip()
    if not tool:
        console.print()
        return
    choice = (
        console.input("[brand]› Nuevo estado (allow/deny/clear): [/brand]")
        .strip()
        .lower()
    )
    if choice == "clear":
        PERMISSIONS.pop(tool, None)
    elif choice in ("allow", "deny"):
        PERMISSIONS[tool] = choice
    save_permissions()
    console.print("[ok]✓ Actualizado.[/ok]\n")


def _download_image(prompt, filename, url):
    r = requests.get(url, timeout=120)
    if r.status_code != 200:
        return None
    with open(filename, "wb") as f:
        f.write(r.content)
    return filename


def generate_image(prompt):
    try:
        filename = f"opencarma_{int(time.time())}.png"
        url = (
            "https://image.pollinations.ai/prompt/"
            + quote(prompt)
            + "?width=1024&height=1024&seed="
            + str(int(time.time()))
        )
        with console.status(
            f"[accent]🎨 {IMG_MODEL_NAME} está generando tu imagen...[/accent]",
            spinner="dots12",
        ):
            return _download_image(prompt, filename, url)
    except Exception as e:
        console.print(f"[err]{e}[/err]")
        return None


def generate_image_flux(prompt):
    try:
        filename = f"opencarma_flux_{int(time.time())}.png"
        url = (
            "https://image.pollinations.ai/prompt/"
            + quote(prompt)
            + "?width=1024&height=1024&model=flux&seed="
            + str(int(time.time()))
        )
        with console.status(
            f"[accent]🎨 {IMG_MODEL_NAME} está generando tu imagen...[/accent]",
            spinner="dots12",
        ):
            return _download_image(prompt, filename, url)
    except Exception as e:
        console.print(f"[err]{e}[/err]")
        return None


def print_image_result(image, prompt, variant):
    if image:
        info = Table.grid(padding=(0, 1))
        info.add_row(
            "[muted]Modelo:[/muted]", f"[accent]{IMG_MODEL_NAME}[/accent] ({variant})"
        )
        info.add_row("[muted]Prompt:[/muted]", prompt)
        info.add_row("[muted]Archivo:[/muted]", f"[ok]{image}[/ok]")
        console.print(
            Panel(
                info,
                title="🖼️  Imagen generada",
                border_style="spring_green3",
                box=box.ROUNDED,
            )
        )
    else:
        console.print(
            Panel(
                f"No se pudo generar la imagen con {IMG_MODEL_NAME}.",
                title="✖ Error",
                border_style="red3",
                box=box.ROUNDED,
            )
        )
    console.print()


# ──────────────────────────────────────────────────────────────────────────
#  Main loop
# ──────────────────────────────────────────────────────────────────────────


def main():
    update_rpc("Iniciando", f"{APP_NAME} CLI")

    banner()
    history = load_history()
    status_bar()

    update_rpc("Esperando comandos", f"{APP_NAME} CLI")

    while True:
        input_panel()
        user_input = console.input("[brand]› [/brand]").strip()

        if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
            update_rpc("Cerrando...", "Hasta luego")
            save_history(history)
            close_rpc()
            console.print("\n[muted]Hasta luego 👋[/muted]\n")
            break

        if user_input.lower() == "/help":
            help_panel()
            continue

        if user_input.lower() == "/perms":
            update_rpc("Gestionando permisos", "/perms")
            show_permissions_menu()
            update_rpc("Esperando comandos", f"{APP_NAME} CLI")
            continue

        if user_input.lower() == "/reset":
            update_rpc("Reiniciando permisos", "/reset")
            reset_permissions()
            update_rpc("Esperando comandos", f"{APP_NAME} CLI")
            continue

        if not user_input:
            continue

        if user_input.startswith("/image "):
            prompt = user_input[7:].strip()
            if not prompt:
                console.print("[err]Uso: /image <prompt>[/err]\n")
                continue

            update_rpc(f"Generando imagen ({IMG_MODEL_NAME})", prompt[:100])
            image = generate_image(prompt)
            print_image_result(image, prompt, "estándar")
            update_rpc("Esperando comandos", f"{APP_NAME} CLI")
            continue

        if user_input.startswith("/flux "):
            prompt = user_input[6:].strip()
            if not prompt:
                console.print("[err]Uso: /flux <prompt>[/err]\n")
                continue

            update_rpc(f"Generando imagen ({IMG_MODEL_NAME} Flux)", prompt[:100])
            image = generate_image_flux(prompt)
            print_image_result(image, prompt, "flux")
            update_rpc("Esperando comandos", f"{APP_NAME} CLI")
            continue

        history.append({"role": "user", "content": user_input})
        console.print(
            Panel(
                user_input,
                title="[user]you[/user]",
                title_align="left",
                border_style="deep_sky_blue1",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

        update_rpc("Pensando...", user_input[:100])

        if "read_file" in user_input.lower() or "leer" in user_input.lower():
            update_rpc("Leyendo archivos", "read_file")
        elif "write_file" in user_input.lower() or "escribir" in user_input.lower():
            update_rpc("Escribiendo archivos", "write_file")
        elif "search" in user_input.lower() or "buscar" in user_input.lower():
            update_rpc("Buscando archivos", "search_files")
        elif "terminal" in user_input.lower() or "cmd" in user_input.lower():
            update_rpc("Ejecutando terminal", "terminal")

        agent_loop(history)

        save_history(history)
        status_bar()

        update_rpc("Esperando comandos", f"{APP_NAME} CLI")


if __name__ == "__main__":
    setup()
    main()
