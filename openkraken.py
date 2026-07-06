import json
import os
import re
import subprocess
import time

from openai import OpenAI, RateLimitError
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt

GITHUB_TOKEN = ""
MODEL = ""
client = None

console = Console()

HISTORY_FILE = "history.json"
PERMISSIONS_FILE = "permissions.json"

# ---------------------------------------------------------------------------
# Permisos (allow / deny), estilo "agente de código"
# ---------------------------------------------------------------------------

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
    """
    Pregunta (o recuerda) si una herramienta puede ejecutarse.
    Devuelve True (permitido) o False (denegado).
    El usuario puede elegir "always" para que quede guardado en permissions.json.
    """
    state = PERMISSIONS.get(tool_name)

    if state == "allow":
        console.print(f"[dim]· permiso recordado: allow → {tool_name}[/dim]")
        return True
    if state == "deny":
        console.print(f"[dim]· permiso recordado: deny → {tool_name}[/dim]")
        return False

    console.print(
        Panel(
            Text(preview, style="bold white"),
            title=f"⚠  Permiso requerido: {tool_name}",
            border_style="yellow",
        )
    )
    console.print(
        "  [bold green]1[/bold green]) Allow once   "
        "[bold green]2[/bold green]) Allow always   "
        "[bold red]3[/bold red]) Deny once   "
        "[bold red]4[/bold red]) Deny always"
    )

    choice = console.input("[bold orange1]  » Elegí una opción (1-4, default 1): [/] ").strip()

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
    return True  # "1" o vacío -> allow once


def reset_permissions():
    global PERMISSIONS
    PERMISSIONS = {}
    if os.path.exists(PERMISSIONS_FILE):
        os.remove(PERMISSIONS_FILE)
    console.print("[green]✓ Permisos reiniciados.[/green]")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup():
    global GITHUB_TOKEN, MODEL, client

    console.print()
    GITHUB_TOKEN = console.input("[bold orange1]GitHub Token:[/] ").strip()
    console.print(
        "[dim]Tip: en GitHub Models los IDs van como 'publisher/modelo', "
        "ej: openai/gpt-4o, deepseek/DeepSeek-R1, meta/Llama-3.3-70B-Instruct[/dim]"
    )
    MODEL = console.input("[bold orange1]Model (ej: openai/gpt-4o):[/] ").strip()

    client = OpenAI(
        api_key=GITHUB_TOKEN,
        base_url="https://models.github.ai/inference",
    )

    load_permissions()
    console.print()


# ---------------------------------------------------------------------------
# Interfaz (banner + barra de estado, inspirados en TUIs tipo OpenCode)
# ---------------------------------------------------------------------------


def banner():
    text = Text()
    text.append(
        r"""
                             __                   __                   _______  ____
  ____ ______   ____   ____ |  | ______________  |  | __ ____   ____   \   _  \/_   |
 /  _ \\____ \_/ __ \ /    \|  |/ /\_  __ \__  \ |  |/ // __ \ /    \  /  /_\  \|   |
(  <_> )  |_> >  ___/|   |  \    <  |  | \// __ \|    <\  ___/|   |  \ \  \_/   \   |
 \____/|   __/ \___  >___|  /__|_ \ |__|  (____  /__|_ \\___  >___|  /  \_____  /___|
       |__|        \/     \/     \/            \/     \/    \/     \/         \/
""",
        style="bold orange1",
    )

    console.print(
        Panel(
            text,
            title="🟧 OpenKraken CLI",
            subtitle="[orange1]Powered by GitHub Models[/orange1]",
            border_style="orange1",
        )
    )


def status_bar():
    """Barra inferior estilo status bar: modelo, cwd y modo de permisos activo."""
    cwd = os.path.basename(os.getcwd()) or os.getcwd()
    allow_count = sum(1 for v in PERMISSIONS.values() if v == "allow")
    deny_count = sum(1 for v in PERMISSIONS.values() if v == "deny")

    left = f"[bold orange1]{MODEL or '—'}[/bold orange1]  ·  [dim]~/{cwd}[/dim]"
    right = f"[green]{allow_count} allow[/green]  [red]{deny_count} deny[/red]  [dim]/perms para gestionar[/dim]"

    console.print(f"{left}{' ' * 4}{right}")
    console.print("[dim]/exit salir · /perms permisos · /reset borrar permisos[/dim]\n")


def input_panel():
    console.print(
        Panel(
            "[dim]Escribí tu mensaje... ej: \"lee config.json y arreglá el bug\"[/dim]",
            border_style="orange1",
            title="[bold orange1]> input[/bold orange1]",
            title_align="left",
        )
    )


# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        {
            "role": "system",
            "content": """
        Eres OpenKraken, un asistente que puede interactuar con el sistema de archivos.

        Tenés disponibles herramientas (function calling): read_file, write_file,
        list_directory, search_files y terminal. Usalas directamente cuando el
        usuario pida leer, escribir, listar o buscar algo, o ejecutar un comando.

        Si en algún momento no tenés function calling disponible, respondé
        únicamente con este formato de JSON en tu mensaje:
        {"tool":"read_file","args":{"path":"archivo"}}
        {"tool":"write_file","args":{"path":"archivo","content":"..."}}
        {"tool":"list_directory","args":{"path":"."}}
        {"tool":"search_files","args":{"keyword":"texto","path":"."}}
        {"tool":"terminal","args":{"command":"ls"}}

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


# ---------------------------------------------------------------------------
# Herramientas (todas pasan por check_permission)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Esquema de tools para function calling nativo (más confiable que pedirle
# al modelo que escriba JSON suelto en el texto)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee y devuelve el contenido de un archivo de texto",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Ruta del archivo"}},
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
                "properties": {"path": {"type": "string", "description": "Ruta del directorio (default '.')"}},
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
                    "path": {"type": "string", "description": "Carpeta donde buscar (default '.')"},
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
                "properties": {"command": {"type": "string", "description": "Comando a ejecutar"}},
                "required": ["command"],
            },
        },
    },
]

# Algunos modelos del catálogo de GitHub Models no soportan function calling
# nativo. Si la API rechaza el parámetro "tools", se cae a este modo texto.
SUPPORTS_TOOLS = True


def _tools_unsupported_error(e):
    msg = str(e).lower()
    return "tool" in msg and ("not support" in msg or "unsupported" in msg or "invalid" in msg or "400" in msg)


def try_parse_tool(text):
    """Fallback: intenta extraer un JSON tool call desde texto plano,
    para modelos que no soportan function calling nativo."""
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


# ---------------------------------------------------------------------------
# Llamadas al modelo (con reintento ante rate limit)
# ---------------------------------------------------------------------------


def chat_with_retry(*args, max_retries=5, **kwargs):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(*args, **kwargs)
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
            console.print(f"[yellow]Rate limited. Esperando {wait}s...[/yellow]")
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Loop principal del agente
# ---------------------------------------------------------------------------


def agent_loop(history, max_tool_steps=25):
    """
    Loop iterativo (no recursivo). Usa function calling nativo cuando el
    modelo lo soporta; si la API lo rechaza, cae automáticamente al modo
    de parseo por texto (try_parse_tool). Cualquier error de la API se
    captura acá y no tumba el programa.
    """
    global SUPPORTS_TOOLS

    for _ in range(max_tool_steps):
        try:
            if SUPPORTS_TOOLS:
                response = chat_with_retry(
                    model=MODEL, messages=history, tools=TOOLS, tool_choice="auto"
                )
            else:
                response = chat_with_retry(model=MODEL, messages=history)
        except Exception as e:
            if SUPPORTS_TOOLS and _tools_unsupported_error(e):
                console.print(
                    "[yellow]⚠ Este modelo no soporta function calling nativo. "
                    "Cambiando a modo texto (JSON en la respuesta).[/yellow]"
                )
                SUPPORTS_TOOLS = False
                continue
            console.print(
                Panel(
                    f"[red]{e}[/red]\n\n"
                    "[dim]Revisá que el nombre del modelo sea válido. En GitHub Models "
                    "suelen ir con formato 'publisher/modelo', ej: openai/gpt-4o, "
                    "deepseek/DeepSeek-R1, meta/Llama-3.3-70B-Instruct.[/dim]",
                    title="✖ Error llamando al modelo",
                    border_style="red",
                )
            )
            return

        message = response.choices[0].message

        # --- Camino 1: function calling nativo ---
        if SUPPORTS_TOOLS and getattr(message, "tool_calls", None):
            if message.content:
                console.print(f"\n[bold orange1]OpenKraken:[/bold orange1] {message.content}\n")

            history.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
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
                console.print(Panel(str(result), title=f"🟧 resultado: {name}", border_style="orange1"))

                history.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

            continue  # dejar que el modelo vea los resultados y siga

        # --- Camino 2: respuesta de texto normal (o fallback JSON-en-texto) ---
        text = message.content or ""
        console.print(f"\n[bold orange1]OpenKraken:[/bold orange1] {text}\n")

        tool_call = None if SUPPORTS_TOOLS else try_parse_tool(text)

        if not tool_call:
            history.append({"role": "assistant", "content": text})
            return

        tool = tool_call["tool"]
        args = tool_call.get("args", {})
        result = run_tool(tool, args)

        console.print(Panel(str(result), title=f"🟧 resultado: {tool}", border_style="orange1"))

        history.append({"role": "assistant", "content": text})
        history.append({"role": "user", "content": f"Tool result:\n{result}\nContinue."})

    console.print("[yellow]⚠ Se alcanzó el límite de pasos de herramientas para este turno.[/yellow]")


# ---------------------------------------------------------------------------
# Comandos de la interfaz (/exit, /perms, /reset)
# ---------------------------------------------------------------------------


def show_permissions_menu():
    if not PERMISSIONS:
        console.print("[dim]No hay permisos guardados todavía.[/dim]\n")
        return

    console.print(Panel("\n".join(f"{k}: {v}" for k, v in PERMISSIONS.items()),
                         title="Permisos guardados", border_style="orange1"))

    tool = console.input("[orange1]Nombre de herramienta a modificar (enter para salir): [/]").strip()
    if not tool:
        return
    choice = console.input("[orange1]Nuevo estado (allow/deny/clear): [/]").strip().lower()
    if choice == "clear":
        PERMISSIONS.pop(tool, None)
    elif choice in ("allow", "deny"):
        PERMISSIONS[tool] = choice
    save_permissions()
    console.print("[green]✓ Actualizado.[/green]\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    banner()
    history = load_history()
    status_bar()

    while True:
        input_panel()
        user_input = console.input("[bold orange1]> [/bold orange1]").strip()

        if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
            save_history(history)
            break

        if user_input.lower() == "/perms":
            show_permissions_menu()
            continue

        if user_input.lower() == "/reset":
            reset_permissions()
            continue

        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})

        agent_loop(history)

        save_history(history)
        status_bar()


if __name__ == "__main__":
    setup()
    main()
