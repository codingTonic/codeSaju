#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote


class FrontendRequestHandler(SimpleHTTPRequestHandler):
    api_base = ""

    def send_head(self):
        """Apply the same path protection and canonical redirects to GET and HEAD."""
        self._jsonld_hashes = []
        path = urlsplit(self.path).path
        self._seo_indexable = self._is_public_page(path)
        if path in {"/", "/index.html", "/app", "/app/index.html"}:
            self.send_response(301)
            # Query strings may contain personal input; never carry them to public URLs.
            self.send_header("Location", "/app/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if path.startswith("/guides/") and path.endswith("/index.html"):
            self.send_response(301)
            self.send_header("Location", path[:-len("index.html")])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if path == "/api-config.js":
            body = (
                "window.__PERSONAL_OS_API_BASE__ = "
                f"{json.dumps(self.api_base)};\n"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return io.BytesIO(body)

        requested = Path(self.translate_path(self.path))
        root = Path(self.directory).resolve()
        if not requested.resolve().is_relative_to(root) or any(
            part.startswith('.') for part in Path(unquote(urlsplit(self.path).path)).parts if part not in ('/', '')
        ):
            self.send_error(404)
            return None
        html_path = requested / "index.html" if requested.is_dir() else requested
        # Permit only the exact static JSON-LD blocks, without relaxing executable scripts.
        if (html_path.suffix == ".html" and html_path.is_file()
                and html_path.resolve().is_relative_to(root) and html_path.stat().st_size < 2_000_000):
            html = html_path.read_text(encoding="utf-8")
            blocks = re.findall(r'<script\b(?=[^>]*\btype=[\"\']application/ld\+json[\"\'])[^>]*>(.*?)</script\s*>', html, re.I | re.S)
            self._jsonld_hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(block.encode("utf-8")).digest()).decode("ascii") + "'" for block in blocks]
        return super().send_head()

    def _is_public_page(self, path: str) -> bool:
        if urlsplit(self.path).query:
            return False
        try:
            manifest = json.loads((Path(self.directory) / "seo-manifest.json").read_text(encoding="utf-8"))
            site = urlsplit(manifest.get("site_url", ""))
            request_host = urlsplit("https://" + self.headers.get("Host", "")).hostname
            # A built production bundle served at a preview host stays noindex.
            public_image = (path.startswith("/app/assets/") or path == "/app/mark.svg") and Path(path).suffix.lower() in {".webp", ".png", ".jpg", ".jpeg", ".svg"}
            return bool(site.scheme == "https" and site.hostname and request_host == site.hostname
                        and (path in manifest.get("public_paths", []) or public_image))
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    def list_directory(self, path):
        self.send_error(404)
        return None

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not getattr(self, "_seo_indexable", False):
            self.send_header("X-Robots-Tag", "noindex, nofollow")
        api = urlsplit(self.api_base)
        api_origin = f"{api.scheme}://{api.netloc}" if api.scheme in {"http", "https"} and api.netloc else ""
        self.send_header("Content-Security-Policy", (
            "default-src 'self'; script-src 'self' " + " ".join(getattr(self, "_jsonld_hashes", [])) + "; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            f"connect-src 'self' {api_origin}; img-src 'self' data: blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        ))
        super().end_headers()

    def log_message(self, format_string: str, *args: object) -> None:
        safe_path = urlsplit(self.path).path
        print(f"{self.client_address[0]} - {self.command} {safe_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Personal OS frontend assets.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--api-base", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api = urlsplit(args.api_base)
    if args.api_base and (api.scheme not in {"http", "https"} or not api.hostname
                         or api.username or api.password or api.query or api.fragment
                         or any(char.isspace() for char in args.api_base)):
        raise ValueError("Invalid API base URL")
    FrontendRequestHandler.api_base = args.api_base.rstrip("/")
    handler = partial(FrontendRequestHandler, directory=str(args.directory.resolve()))

    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f"Serving frontend on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
