"""Tests for NRO256 portal catalog generation, Zero-JS structure, accessibility, and security."""

from __future__ import annotations

import copy
import functools
import http.server
import json
import sys
import threading
import unittest
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sync_apps


class HtmlStructureInspector(HTMLParser):
    """Collect structural, accessibility, and asset metadata from index.html."""

    def __init__(self) -> None:
        super().__init__()
        self.headings: list[int] = []
        self.ids: set[str] = set()
        self.landmarks: set[str] = set()
        self.skip_links: list[str] = []
        self.internal_anchors: list[str] = []
        self.external_links: list[dict[str, str]] = []
        self.card_action_labels: list[tuple[str, str]] = []
        self.local_refs: list[str] = []
        self.canonical_href: str = ""
        self.og_url: str = ""
        self._in_card_action_link = False
        self._current_link_aria = ""
        self._current_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: (v or "") for k, v in attrs}
        if attr_map.get("id"):
            self.ids.add(attr_map["id"])

        if tag in ("header", "nav", "main", "footer"):
            self.landmarks.add(tag)

        if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            self.headings.append(int(tag[1]))

        if tag == "link":
            rel = attr_map.get("rel", "")
            href = attr_map.get("href", "")
            if rel == "canonical":
                self.canonical_href = href
            if href.startswith("./"):
                self.local_refs.append(href)

        if tag == "meta" and attr_map.get("property") == "og:url":
            self.og_url = attr_map.get("content", "")

        if tag in ("script", "img"):
            src = attr_map.get("src", "")
            if src.startswith("./"):
                self.local_refs.append(src)

        if tag == "a":
            href = attr_map.get("href", "")
            classes = attr_map.get("class", "").split()
            if href.startswith("#") and len(href) > 1:
                self.internal_anchors.append(href[1:])
            if "skip-link" in classes and href.startswith("#"):
                self.skip_links.append(href[1:])
            if attr_map.get("target") == "_blank":
                self.external_links.append(attr_map)
            if attr_map.get("target") == "_blank" and any(
                c in classes for c in ("btn--download", "action-link")
            ):
                self._in_card_action_link = True
                self._current_link_aria = attr_map.get("aria-label", "")
                self._current_link_text = []

    def handle_data(self, data: str) -> None:
        if self._in_card_action_link:
            self._current_link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_card_action_link:
            visible_text = " ".join("".join(self._current_link_text).split())
            self.card_action_labels.append((visible_text, self._current_link_aria))
            self._in_card_action_link = False


class SubpathPortalHandler(http.server.SimpleHTTPRequestHandler):
    """Serve portal directory under both / and /portal/ for GitHub Pages testing."""

    def translate_path(self, path: str) -> str:
        clean_path = path.split("?", 1)[0].split("#", 1)[0]
        if clean_path == "/portal":
            clean_path = "/portal/"
        if clean_path.startswith("/portal/"):
            clean_path = clean_path[len("/portal") :]
        return super().translate_path(clean_path)

    def log_message(self, format: str, *args: object) -> None:
        return


class PortalTests(unittest.TestCase):
    """Verify sync script safety, Zero-JS layout, HTML accessibility, and HTTP serving."""

    def setUp(self) -> None:
        self.catalog = json.loads((ROOT_DIR / "data" / "apps.json").read_text(encoding="utf-8"))
        self.index_html = (ROOT_DIR / "index.html").read_text(encoding="utf-8")

    def test_sync_check_passes_on_repository(self) -> None:
        self.assertEqual(sync_apps.main(["--check"]), 0)

    def test_zero_js_and_search_abolished(self) -> None:
        self.assertFalse((ROOT_DIR / "js" / "app.js").exists())
        self.assertFalse((ROOT_DIR / "js").exists())
        self.assertNotIn("<script", self.index_html.lower())
        self.assertNotIn("app-search", self.index_html)
        self.assertNotIn("data-search", self.index_html)

    def test_html_escape_and_scheme_validation(self) -> None:
        sample = copy.deepcopy(self.catalog)
        sample["apps"][0]["summary"] = '危険 <script>alert("x")</script> & 確認'
        rendered = sync_apps.render_apps_html(sample)
        self.assertNotIn('<script>alert("x")</script>', rendered)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; 確認", rendered)

        bad_scheme = copy.deepcopy(self.catalog)
        bad_scheme["apps"][0]["releaseUrl"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            sync_apps.validate_catalog(bad_scheme)

        http_scheme = copy.deepcopy(self.catalog)
        http_scheme["apps"][0]["repoUrl"] = "http://github.com/NRO256/p2f"
        with self.assertRaises(ValueError):
            sync_apps.validate_catalog(http_scheme)

        bad_admin = copy.deepcopy(self.catalog)
        bad_admin["apps"][0]["requiresAdmin"] = "false"
        with self.assertRaises(TypeError):
            sync_apps.validate_catalog(bad_admin)

        bad_size = copy.deepcopy(self.catalog)
        bad_size["apps"][0]["binarySize"] = "unknown"
        with self.assertRaises(ValueError):
            sync_apps.validate_catalog(bad_size)

    def test_screenshot_conditional_rendering(self) -> None:
        default_rendered = sync_apps.render_apps_html(self.catalog)
        self.assertNotIn("<figure", default_rendered)

        with_shot = copy.deepcopy(self.catalog)
        with_shot["apps"][0]["screenshot"] = "images/p2f.png"
        with_shot["apps"][0]["screenshotAlt"] = "P2F のメイン画面"
        rendered = sync_apps.render_apps_html(with_shot)
        self.assertIn('<figure class="app-entry__media">', rendered)
        self.assertIn('src="./images/p2f.png"', rendered)
        self.assertIn('alt="P2F のメイン画面"', rendered)

        missing_alt = copy.deepcopy(self.catalog)
        missing_alt["apps"][0]["screenshot"] = "images/p2f.png"
        missing_alt["apps"][0]["screenshotAlt"] = ""
        with self.assertRaises(ValueError):
            sync_apps.validate_catalog(missing_alt)

    def test_index_html_structure_and_accessibility(self) -> None:
        inspector = HtmlStructureInspector()
        inspector.feed(self.index_html)

        self.assertEqual(inspector.headings.count(1), 1)
        for prev, curr in zip(inspector.headings, inspector.headings[1:]):
            self.assertLessEqual(curr - prev, 1, f"Heading jump detected: h{prev} -> h{curr}")

        self.assertEqual(inspector.landmarks, {"header", "nav", "main", "footer"})
        self.assertTrue(inspector.skip_links)
        for target_id in inspector.skip_links:
            self.assertIn(target_id, inspector.ids)
        for anchor_id in inspector.internal_anchors:
            self.assertIn(anchor_id, inspector.ids, f"Broken internal anchor: #{anchor_id}")

        self.assertEqual(inspector.canonical_href, "https://nro256.github.io/portal/")
        self.assertEqual(inspector.og_url, "https://nro256.github.io/portal/")

        for link in inspector.external_links:
            rel_tokens = set(link.get("rel", "").split())
            self.assertIn("noopener", rel_tokens)
            self.assertIn("noreferrer", rel_tokens)

        self.assertEqual(len(inspector.card_action_labels), 18)
        aria_labels = [aria for _, aria in inspector.card_action_labels]
        self.assertEqual(len(aria_labels), len(set(aria_labels)), "Duplicate card link aria-label")
        for visible, aria in inspector.card_action_labels:
            self.assertTrue(aria.startswith(visible), f"Label-in-Name mismatch: {visible} vs {aria}")

        for ref in inspector.local_refs:
            target = ROOT_DIR / ref[2:]
            self.assertTrue(target.is_file(), f"Missing local asset: {ref}")

    def test_404_page_self_contained_and_return_link(self) -> None:
        html_404 = (ROOT_DIR / "404.html").read_text(encoding="utf-8")
        self.assertIn('href="/portal/"', html_404)
        self.assertIn("<style>", html_404)
        self.assertNotIn("css/style.css", html_404)

    def test_no_local_paths_or_draft_leaks(self) -> None:
        forbidden = ("C:\\Users", "C:/Users", "C:\\Antigravity", "C:/Antigravity", "x_post.txt")
        check_targets = [
            "index.html",
            "404.html",
            "css/style.css",
            "data/apps.json",
            "scripts/sync_apps.py",
        ]
        if (ROOT_DIR / "README.md").is_file():
            check_targets.append("README.md")

        for rel in check_targets:
            content = (ROOT_DIR / rel).read_text(encoding="utf-8")
            for needle in forbidden:
                self.assertNotIn(needle, content, f"Forbidden string {needle!r} in {rel}")

    def test_http_serving_under_root_and_portal_subpath(self) -> None:
        handler = functools.partial(SubpathPortalHandler, directory=str(ROOT_DIR))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            port = server.server_address[1]
            paths = [
                "/",
                "/portal/",
                "/portal/css/style.css",
                "/portal/data/apps.json",
                "/portal/images/favicon.svg",
                "/portal/404.html",
            ]
            for req_path in paths:
                url = f"http://127.0.0.1:{port}{req_path}"
                with opener.open(url, timeout=5) as resp:
                    self.assertEqual(resp.status, 200, f"Unexpected HTTP status for {req_path}")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
