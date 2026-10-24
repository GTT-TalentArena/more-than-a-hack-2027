"""Loopback HTTP transport with a fixed asset allowlist and read-only frame API."""

import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlsplit

from .estimation import estimated_window, MAX_GAP_SECONDS, GRACE_SECONDS
from .predictions import load_predictions
from .synthetic import SyntheticTracking
from .tracking import IndexedTracking, ViewerError

STATIC = Path(__file__).with_name("static")
ASSETS = {"/": ("index.html", "text/html"), "/styles.css": ("styles.css", "text/css"),
          "/viewer.js": ("viewer.js", "text/javascript"),
          "/playback.mjs": ("playback.mjs", "text/javascript")}
for font in ("geist-latin", "geist-mono-latin", "bricolage-latin", "instrument-serif-italic-latin"):
    ASSETS["/fonts/" + font + ".woff2"] = ("fonts/" + font + ".woff2", "font/woff2")
MAX_BLOCK = 250


class Session:
    def __init__(self):
        self.source = None
        self.labels = None
        self.progress = 0.0
        self.error = None
        self.ready = threading.Event()

    def load(self, meta=None, raw=None, predictions=None, no_predictions=False):
        try:
            if raw is None:
                self.source = SyntheticTracking()
            else:
                self.source = IndexedTracking(meta, raw, lambda value: setattr(self, "progress", value))
            if predictions is not None:
                self.labels = load_predictions(predictions, self.source.n_frames)
            elif self.source.synthetic and not no_predictions:
                self.labels = [self.source.label(i) for i in range(self.source.n_frames)]
            self.progress = 1.0
        except ViewerError as error:
            self.error = str(error)
        except Exception:
            self.error = "Could not initialise the source. Verify local inputs and restart."
        finally:
            self.ready.set()

    def metadata(self):
        if not self.ready.is_set():
            return {"status": "loading", "progress": self.progress}
        if self.error:
            return {"status": "error", "message": self.error}
        source = self.source
        return {"status": "ready", "synthetic": source.synthetic, "n_frames": source.n_frames,
                "initial_frame": 0 if source.synthetic else min(source.n_frames - 1, source.blocks[0][1]),
                "fps": source.fps, "pitch": source.pitch, "blocks": source.blocks,
                "teams": list(source.names), "slot_ids": source.slot_ids, "slot_teams": source.teams,
                "has_predictions": self.labels is not None,
                "player_estimation_max_gap_seconds": MAX_GAP_SECONDS,
                "player_estimation_grace_seconds": GRACE_SECONDS,
                "index_seconds": round(source.load_seconds, 3),
                "index_bytes": len(source.offsets) * source.offsets.itemsize if hasattr(source, "offsets") else 0}

    def label_context(self, frame):
        """Original model labels over the last 40 video seconds, within this half.

        These are descriptive window counts, not official evaluation metrics. X is
        preserved and no observation or team hypothesis is inferred from the labels.
        """
        block = next((block for block in self.source.blocks if block[1] <= frame <= block[2]), None)
        start = max(block[1], frame - self.source.fps * 40 + 1) if block else frame
        result = {"start_frame": start, "end_frame": frame + 1, "spells": [], "home_percent": None}
        if self.labels is None:
            return result
        labels = self.labels[start:frame + 1]
        spells = result["spells"]
        for index, label in enumerate(labels, start):
            if spells and spells[-1]["label"] == label:
                spells[-1]["end_frame"] = index + 1
            else:
                spells.append({"label": label, "start_frame": index, "end_frame": index + 1})
        home, away = labels.count("H"), labels.count("A")
        if home + away:
            result["home_percent"] = round(100 * home / (home + away))
        return result


def make_server(session, port=8765):
    class ViewerServer(ThreadingHTTPServer):
        # Windows SO_REUSEADDR can let two old/new viewers share a port and serve
        # inconsistent code. Exclusive binding makes a restart deterministic.
        allow_reuse_address = not hasattr(socket, 'SO_EXCLUSIVEADDRUSE')

        def server_bind(self):
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never persist URLs, input paths or frame requests.

        def respond(self, code, content, content_type="application/json"):
            body = json.dumps(content, allow_nan=False).encode() if content_type == "application/json" else content
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self'; "
                             "style-src 'self'; script-src 'self'; font-src 'self'; object-src 'none'; "
                             "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_GET(self):
            expected_host = "127.0.0.1:{}".format(self.server.server_port)
            # Block DNS rebinding and cross-site access to local data; no CORS headers.
            if self.headers.get("Host") != expected_host or self.headers.get("Origin", "http://" + expected_host) != "http://" + expected_host:
                self.respond(403, {"message": "Only the viewer's loopback origin is allowed."})
                return
            if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
                self.respond(403, {"message": "Cross-site access is disabled."})
                return
            url = urlsplit(self.path)
            if url.path in ASSETS and not url.query:
                filename, mime = ASSETS[url.path]
                self.respond(200, (STATIC / filename).read_bytes(), mime)
            elif url.path == "/api/meta" and not url.query:
                self.respond(200, session.metadata())
            elif url.path == "/api/frames":
                if not session.ready.is_set() or session.error:
                    self.respond(409, {"message": "The source is not ready."})
                    return
                try:
                    query = parse_qs(url.query, strict_parsing=True)
                    if set(query) != {"start", "count"} or any(len(values) != 1 for values in query.values()):
                        raise ValueError
                    start, count = int(query["start"][0]), int(query["count"][0])
                    if not 0 <= start < session.source.n_frames or not 1 <= count <= MAX_BLOCK:
                        raise ValueError
                except ValueError:
                    self.respond(400, {"message": "Invalid frame window (maximum 250 frames)."})
                    return
                try:
                    rows = estimated_window(session.source, start, count)
                    for row in rows:
                        row["label"] = None if session.labels is None else session.labels[row["frame"]]
                    self.respond(200, {"frames": rows})
                except ViewerError as error:
                    self.respond(409, {"message": str(error)})
            elif url.path == "/api/context":
                if not session.ready.is_set() or session.error:
                    self.respond(409, {"message": "The source is not ready."})
                    return
                try:
                    query = parse_qs(url.query, strict_parsing=True)
                    if set(query) != {"frame"} or len(query["frame"]) != 1:
                        raise ValueError
                    frame = int(query["frame"][0])
                    if not 0 <= frame < session.source.n_frames:
                        raise ValueError
                except ValueError:
                    self.respond(400, {"message": "Invalid context frame."})
                    return
                self.respond(200, session.label_context(frame))
            else:
                self.respond(404, {"message": "Resource not available."})

    return ViewerServer(("127.0.0.1", port), Handler)
