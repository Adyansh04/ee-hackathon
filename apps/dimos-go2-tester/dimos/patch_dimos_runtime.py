from pathlib import Path

import dimos
import dimos.robot.unitree.connection as unitree_connection


DIMOS_DIR = Path(dimos.__file__).resolve().parent


def patch_unitree_aes() -> None:
    path = Path(unitree_connection.__file__)
    text = path.read_text(encoding="utf-8")

    if "from pathlib import Path" not in text:
        text = text.replace("import functools\n", "import functools\nfrom pathlib import Path\n")

    if "import os" not in text:
        text = text.replace("import numpy as np\n", "import os\n\nimport numpy as np\n")

    helper = '''\
def _read_optional_key_file(path: str) -> str | None:
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


'''

    if "def _read_optional_key_file(" not in text:
        marker = "VideoMessage: TypeAlias = NDArray[np.uint8]  # Shape: (height, width, 3)\n\n\n"
        text = text.replace(marker, marker + helper)

    old = "        self.conn = LegionConnection(WebRTCConnectionMethod.LocalSTA, ip=self.ip)\n"
    new = '''\
        aes_128_key = (
            os.environ.get("UNITREE_AES_128_KEY")
            or os.environ.get("GO2_AES_128_KEY")
            or _read_optional_key_file(os.environ.get("UNITREE_AES_KEY_FILE", "/data/dimos/unitree_aes_key"))
        )
        self.conn = LegionConnection(
            WebRTCConnectionMethod.LocalSTA,
            ip=self.ip,
            aes_128_key=aes_128_key,
        )
'''

    if "UNITREE_AES_128_KEY" not in text:
        if old not in text:
            raise SystemExit(f"DimOS Unitree AES patch target not found in {path}")
        text = text.replace(old, new)

    path.write_text(text, encoding="utf-8")
    print(f"Patched Unitree AES key support in {path}")


def patch_agentic_web_import() -> None:
    api_dir = DIMOS_DIR / "web" / "dimos_interface" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    for init_file in [
        DIMOS_DIR / "web" / "dimos_interface" / "__init__.py",
        api_dir / "__init__.py",
    ]:
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

    server = api_dir / "server.py"
    if server.exists():
        print(f"Agentic web import target already exists at {server}")
        return

    server.write_text(
        '''\
"""Compatibility shim for DimOS wheels missing dimos.web.dimos_interface."""

from dimos.web.fastapi_server import FastAPIServer as _BaseFastAPIServer


class FastAPIServer(_BaseFastAPIServer):
    def __init__(
        self,
        dev_name: str = "FastAPI Server",
        edge_type: str = "Bidirectional",
        host: str | None = None,
        port: int = 5555,
        text_streams=None,
        audio_subject=None,
        **streams,
    ) -> None:
        self.audio_subject = audio_subject
        super().__init__(
            dev_name=dev_name,
            edge_type=edge_type,
            host=host,
            port=port,
            text_streams=text_streams,
            **streams,
        )
''',
        encoding="utf-8",
    )
    print(f"Patched agentic web import shim in {server}")


def patch_rerun_dashboard() -> None:
    dashboard = DIMOS_DIR / "web" / "templates" / "rerun_dashboard.html"
    if not dashboard.exists():
        print(f"Skipped dashboard patch; missing {dashboard}")
        return

    dashboard.write_text(
        '''\
<!DOCTYPE html>
<html>
<head>
    <title>Dimos Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { width: 100%; height: 100%; overflow: hidden; }
        body { background: #0a0a0f; font-family: -apple-system, system-ui, sans-serif; }
        :root { --command-center-width: max(30vw, 35rem); }
        .container { display: flex; width: 100%; height: 100%; }
        .command-center {
            width: var(--command-center-width);
            min-width: 16rem;
            border: none;
            border-right: 1px solid #333;
        }
        .rerun { flex: 1 1 auto; border: none; min-width: 0; }
        .divider {
            width: 6px;
            background: linear-gradient(180deg, #202530 0%, #141824 100%);
            cursor: col-resize;
            border-left: 1px solid #0f1016;
            border-right: 1px solid #0f1016;
        }
        .divider:hover { background: #2a3140; }
        .divider.dragging { background: #3a4458; }
        body.dragging { user-select: none; cursor: col-resize; }
    </style>
</head>
<body>
    <div class="container">
        <iframe class="command-center" src="/command-center"></iframe>
        <div class="divider" role="separator" aria-label="Resize panels"></div>
        <iframe class="rerun" id="rerun-frame"></iframe>
    </div>
    <script>
        (function () {
            const host = window.location.hostname;
            const rerunUrl = "rerun+http://" + host + ":9876/proxy";
            const localViewer = "http://" + host + ":9090/?url=" + encodeURIComponent(rerunUrl);
            const hostedViewer = "https://app.rerun.io/?url=" + encodeURIComponent(rerunUrl);
            document.getElementById("rerun-frame").src =
                localViewer;

            const links = document.createElement("div");
            links.style.cssText = "position:fixed;right:12px;top:10px;z-index:20;display:flex;gap:8px;font:12px -apple-system,system-ui,sans-serif;";
            links.innerHTML =
                '<a href="/command-center" target="_blank" style="color:#dce6ff;background:#111827cc;border:1px solid #384152;padding:6px 8px;text-decoration:none">Command Center</a>' +
                '<a href="' + localViewer + '" target="_blank" style="color:#dce6ff;background:#111827cc;border:1px solid #384152;padding:6px 8px;text-decoration:none">Rerun Local</a>' +
                '<a href="' + hostedViewer + '" target="_blank" style="color:#dce6ff;background:#111827cc;border:1px solid #384152;padding:6px 8px;text-decoration:none">Rerun Hosted</a>';
            document.body.appendChild(links);

            const container = document.querySelector(".container");
            const divider = document.querySelector(".divider");
            const commandCenter = document.querySelector(".command-center");
            const body = document.body;
            const minWidth = 0;

            let isDragging = false;
            let pointerId = null;

            function onPointerMove(event) {
                if (!isDragging) return;
                const rect = container.getBoundingClientRect();
                const dividerWidth = divider.getBoundingClientRect().width;
                const available = event.clientX - rect.left - dividerWidth / 2;
                const nextWidth = Math.max(minWidth, Math.min(available, rect.width));
                commandCenter.style.width = `${nextWidth}px`;
                document.documentElement.style.setProperty("--command-center-width", `${nextWidth}px`);
            }

            function stopDragging() {
                if (!isDragging) return;
                isDragging = false;
                divider.classList.remove("dragging");
                body.classList.remove("dragging");
                window.removeEventListener("pointermove", onPointerMove);
                window.removeEventListener("pointerup", stopDragging);
                if (pointerId !== null) {
                    divider.releasePointerCapture(pointerId);
                    pointerId = null;
                }
            }

            divider.addEventListener("pointerdown", (event) => {
                event.preventDefault();
                isDragging = true;
                pointerId = event.pointerId;
                divider.setPointerCapture(pointerId);
                divider.classList.add("dragging");
                body.classList.add("dragging");
                window.addEventListener("pointermove", onPointerMove);
                window.addEventListener("pointerup", stopDragging);
            });
        })();
    </script>
</body>
</html>
''',
        encoding="utf-8",
    )
    print(f"Patched Rerun dashboard for remote LAN access in {dashboard}")


def patch_rerun_bridge_cors() -> None:
    bridge = DIMOS_DIR / "visualization" / "rerun" / "bridge.py"
    if not bridge.exists():
        print(f"Skipped Rerun bridge CORS patch; missing {bridge}")
        return

    text = bridge.read_text(encoding="utf-8")
    replacements = [
        (
            "server_uri = rr.serve_grpc()",
            'server_uri = rr.serve_grpc(cors_allow_origin=["*"])\n'
            '            logger.info("Rerun gRPC server started", server_uri=server_uri)',
        ),
        (
            "rr.serve_web_viewer(connect_to=server_uri, open_browser=False)",
            "rr.serve_web_viewer(\n"
            "                web_port=self.config.web_port,\n"
            "                connect_to=server_uri,\n"
            "                open_browser=False,\n"
            "            )\n"
            '            logger.info("Rerun web viewer started", web_port=self.config.web_port)',
        ),
    ]

    changed = False
    for old, new in replacements:
        if old in text and new not in text:
            text = text.replace(old, new)
            changed = True

    if changed:
        bridge.write_text(text, encoding="utf-8")
        print(f"Patched Rerun bridge web serving in {bridge}")
    else:
        print(f"Rerun bridge web serving patch already present or target missing in {bridge}")


def patch_agentic_web_input_text_fallback() -> None:
    web_input = DIMOS_DIR / "agents" / "web_human_input.py"
    if not web_input.exists():
        print(f"Skipped WebInput text fallback patch; missing {web_input}")
        return

    text = web_input.read_text(encoding="utf-8")
    old = '''\
        normalizer = AudioNormalizer()

        # Here to prevent unwanted imports in the file.
        from dimos.stream.audio.stt.node_whisper import WhisperNode

        stt_node = WhisperNode()

        # Connect audio pipeline: browser audio \u2192 normalizer \u2192 whisper
        normalizer.consume_audio(audio_subject.pipe(ops.share()))
        stt_node.consume_audio(normalizer.emit_audio())

        # Subscribe to both text input sources
        # 1. Direct text from web interface
        unsub = self._web_interface.query_stream.subscribe(self._human_transport.publish)
        self.register_disposable(unsub)

        # 2. Transcribed text from STT
        unsub = stt_node.emit_text().subscribe(self._human_transport.publish)
        self.register_disposable(unsub)
'''
    new = '''\
        # Subscribe to direct text input from the web interface.
        unsub = self._web_interface.query_stream.subscribe(self._human_transport.publish)
        self.register_disposable(unsub)

        try:
            normalizer = AudioNormalizer()

            # Here to prevent unwanted imports in the file.
            from dimos.stream.audio.stt.node_whisper import WhisperNode

            stt_node = WhisperNode()

            # Connect audio pipeline: browser audio -> normalizer -> whisper
            normalizer.consume_audio(audio_subject.pipe(ops.share()))
            stt_node.consume_audio(normalizer.emit_audio())

            # Transcribed text from STT.
            unsub = stt_node.emit_text().subscribe(self._human_transport.publish)
            self.register_disposable(unsub)
        except ImportError as exc:
            logger.warning(f"Whisper backend unavailable; web agent input is text-only: {exc}")
'''

    if "web agent input is text-only" in text:
        print(f"WebInput text fallback patch already present in {web_input}")
        return

    if old not in text:
        print(f"Skipped WebInput text fallback patch; target block missing in {web_input}")
        return

    web_input.write_text(text.replace(old, new), encoding="utf-8")
    print(f"Patched WebInput text-only fallback in {web_input}")


patch_unitree_aes()
patch_agentic_web_import()
patch_rerun_dashboard()
patch_rerun_bridge_cors()
patch_agentic_web_input_text_fallback()
