"""Serve the Pages build locally and rebuild saved sources without publishing."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import unquote, urlsplit

if __package__:
    from .documentation_site import OUTPUT, ROOT
else:
    from documentation_site import OUTPUT, ROOT


def source_snapshot(root: Path = ROOT) -> str:
    """Observe authored inputs, not outputs, caches or dependency installs."""
    paths = set((root / "docs").rglob("*"))
    paths.update((root / "ontology").glob("*.ttl"))
    paths.update((root / "products").glob("*/specs/*.ttl"))
    paths.update((root / "tools").glob("*.py"))
    paths.add(root / "tools" / "ontology_relationship_graph.html")
    paths.update((root / "tools" / "vendor" / "archify").rglob("*"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        if not path.is_file() or "node_modules" in path.parts or "__pycache__" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@dataclass
class PreviewState:
    version: int = 0
    building: bool = False
    error: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def status(self) -> dict:
        with self.lock:
            return {"version": self.version, "building": self.building, "error": self.error}

    def rebuild(self, command: list[str] | None = None) -> bool:
        with self.lock:
            self.building = True
        try:
            result = subprocess.run(
                command or [sys.executable, str(ROOT / "tools" / "build_documentation_site.py"), "--quick"],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600,
            )
            if result.returncode:
                raise RuntimeError((result.stdout + result.stderr).strip())
            with self.lock:
                self.version += 1
                self.error = ""
            print("Vorschau aktualisiert.", flush=True)
            return True
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
            with self.lock:
                self.error = str(error)[-12000:]
            print(f"Build fehlgeschlagen; letzte gültige Ansicht bleibt erhalten:\n{error}", flush=True)
            return False
        finally:
            with self.lock:
                self.building = False


def watch(state: PreviewState, stop: threading.Event) -> None:
    previous = source_snapshot()
    while not stop.wait(0.5):
        try:
            current = source_snapshot()
            if current == previous:
                continue
            if stop.wait(0.25):
                break
            previous = source_snapshot()
            state.rebuild()
        except OSError:
            # A source can disappear briefly during an editor's atomic save.
            continue


def preview_script(base_path: str) -> str:
    endpoint = json.dumps(base_path + "__preview/status")
    return """<script data-local-preview>
(() => {
  let version;
  const notice = document.createElement('aside');
  notice.setAttribute('role', 'status');
  notice.style.cssText = 'position:fixed;bottom:12px;left:12px;right:12px;z-index:99999;padding:12px 16px;border:1px solid #b45c21;border-radius:10px;background:var(--surface,#fff);color:var(--ink,#172432);box-shadow:0 8px 30px #0002;max-height:35vh;overflow:auto;white-space:pre-wrap;font:13px/1.5 system-ui;display:none';
  document.body.append(notice);
  async function poll() {
    try {
      const response = await fetch(ENDPOINT, {cache: 'no-store'});
      const state = await response.json();
      if (version !== undefined && state.version !== version) { location.reload(); return; }
      version = state.version;
      notice.textContent = state.error ? 'Lokaler Build fehlgeschlagen – letzte gültige Ansicht:\\n' + state.error : state.building ? 'Lokale Vorschau wird aktualisiert …' : '';
      notice.style.display = notice.textContent ? 'block' : 'none';
    } catch { /* A server restart does not affect the last rendered page. */ }
    setTimeout(poll, 1000);
  }
  poll();
})();</script>""".replace("ENDPOINT", endpoint)


def handler_for(state: PreviewState, base_path: str = "/", output: Path = OUTPUT):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output), **kwargs)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == base_path + "__preview/status":
                payload = json.dumps(state.status(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if not path.startswith(base_path):
                self.send_error(404)
                return
            relative = unquote(path[len(base_path):])
            candidate = (output / relative).resolve()
            if not candidate.is_relative_to(output.resolve()):
                self.send_error(403)
                return
            if candidate.is_dir():
                if not path.endswith("/"):
                    query = urlsplit(self.path).query
                    self.send_response(301)
                    self.send_header("Location", path + "/" + ("?" + query if query else ""))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                candidate /= "index.html"
            if candidate.suffix == ".html" and candidate.is_file():
                markup = candidate.read_text(encoding="utf-8")
                if 'class="site-header"' in markup:
                    markup = markup.replace("</body>", preview_script(base_path) + "</body>", 1)
                payload = markup.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            original = self.path
            self.path = "/" + relative + ("?" + urlsplit(original).query if urlsplit(original).query else "")
            super().do_GET()

        def log_message(self, format, *args):
            if len(args) > 1 and str(args[1]).startswith("4"):
                super().log_message(format, *args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--base-path", default="/", help="Simulate a Pages prefix, e.g. /spec-compiler/")
    args = parser.parse_args()
    base = "/" + args.base_path.strip("/") + "/" if args.base_path.strip("/") else "/"
    state = PreviewState()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(state, base))
    if not state.rebuild() and not (OUTPUT / "index.html").is_file():
        server.server_close()
        raise SystemExit("Keine gültige Dokumentationswebsite vorhanden.")
    stop = threading.Event()
    watcher = threading.Thread(target=watch, args=(state, stop), daemon=True)
    watcher.start()
    print(f"Lokale Vorschau: http://127.0.0.1:{args.port}{base} (Speichern aktualisiert; kein Deployment)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        watcher.join(timeout=2)


if __name__ == "__main__":
    main()
