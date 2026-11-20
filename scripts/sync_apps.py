"""Synchronize portal HTML sections from data/apps.json."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REQUIRED_APP_FIELDS = (
    "id",
    "name",
    "version",
    "category",
    "categoryLabel",
    "uiType",
    "os",
    "binaryName",
    "binarySize",
    "permissionLabel",
    "summary",
    "repoUrl",
    "releaseUrl",
    "issuesUrl",
)

URL_FIELDS = ("repoUrl", "releaseUrl", "issuesUrl")

ICON_DOWNLOAD = (
    '<svg class="btn__icon" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 3v12"/>'
    '<path d="m7 10 5 5 5-5"/>'
    '<path d="M5 21h14"/>'
    "</svg>"
)

ICON_EXTERNAL = (
    '<svg class="btn__icon" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M15 3h6v6"/>'
    '<path d="M10 14 21 3"/>'
    '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    "</svg>"
)


def esc(value: Any) -> str:
    """Escape HTML text and attribute quotes safely."""
    return html.escape(str(value), quote=True)


def validate_https_url(url: str, field_name: str, app_id: str) -> None:
    """Ensure external URLs use https scheme and include a host."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError(f"Invalid https URL in {app_id}.{field_name}: {url!r}")


def validate_screenshot_path(path_str: str, alt_text: str, app_id: str) -> None:
    """Validate optional relative screenshot path and required alt text."""
    if not path_str:
        return
    if not alt_text.strip():
        raise ValueError(f"Missing screenshotAlt for {app_id} when screenshot is set")
    lower = path_str.lower()
    if lower.startswith(("http://", "https://", "javascript:", "data:", "//")):
        raise ValueError(f"Screenshot must be a local relative path in {app_id}: {path_str!r}")
    if path_str.startswith("/") or ".." in Path(path_str).parts:
        raise ValueError(f"Unsafe relative screenshot path in {app_id}: {path_str!r}")


def validate_catalog(data: dict[str, Any]) -> None:
    """Validate catalog structure, categories, URLs, and app metadata."""
    categories = data.get("categories")
    apps = data.get("apps")
    if not isinstance(categories, list) or not categories:
        raise ValueError("Catalog must contain a non-empty 'categories' list")
    if not isinstance(apps, list) or not apps:
        raise ValueError("Catalog must contain a non-empty 'apps' list")

    category_ids: set[str] = set()
    for cat in categories:
        cat_id = str(cat.get("id", "")).strip()
        cat_label = str(cat.get("label", "")).strip()
        if not cat_id or not cat_label:
            raise ValueError(f"Invalid category definition: {cat!r}")
        category_ids.add(cat_id)

    seen_ids: set[str] = set()
    for app in apps:
        app_id = str(app.get("id", "")).strip()
        for field in REQUIRED_APP_FIELDS:
            if not str(app.get(field, "")).strip():
                raise ValueError(f"Missing required field '{field}' in app {app_id or app!r}")
        if app_id in seen_ids:
            raise ValueError(f"Duplicate app id: {app_id}")
        seen_ids.add(app_id)

        if app["category"] not in category_ids:
            raise ValueError(f"Unknown category '{app['category']}' in {app_id}")
        if app["uiType"] not in ("GUI", "CLI"):
            raise ValueError(f"Invalid uiType '{app['uiType']}' in {app_id}")
        if not isinstance(app.get("requiresAdmin"), bool):
            raise TypeError(f"requiresAdmin must be boolean in {app_id}")

        highlights = app.get("highlights")
        if not isinstance(highlights, list) or not highlights:
            raise ValueError(f"highlights must be a non-empty list in {app_id}")

        for url_field in URL_FIELDS:
            validate_https_url(str(app[url_field]), url_field, app_id)

        validate_screenshot_path(
            str(app.get("screenshot", "")),
            str(app.get("screenshotAlt", "")),
            app_id,
        )


def sorted_apps(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return apps ordered deterministically by order then name."""
    return sorted(
        data["apps"],
        key=lambda item: (int(item.get("order", 9999)), str(item.get("name", ""))),
    )


def render_filters_html(data: dict[str, Any]) -> str:
    """Render category filter buttons with live counts."""
    apps = data["apps"]
    counts = Counter(app["category"] for app in apps)
    lines = [
        (
            '<button type="button" class="filter-btn" data-category="all" aria-pressed="true">'
            f'すべて <span class="filter-btn__count">({len(apps)})</span>'
            "</button>"
        )
    ]
    for cat in data["categories"]:
        cat_id = esc(cat["id"])
        cat_label = esc(cat["label"])
        cat_count = counts.get(cat["id"], 0)
        lines.append(
            f'<button type="button" class="filter-btn" data-category="{cat_id}" aria-pressed="false">'
            f'{cat_label} <span class="filter-btn__count">({cat_count})</span>'
            "</button>"
        )
    return "\n            ".join(lines)


def build_search_blob(app: dict[str, Any]) -> str:
    """Build plain search index string for client-side NFKC filtering."""
    parts = [
        str(app["id"]),
        str(app["name"]),
        str(app.get("shortName", "")),
        str(app["categoryLabel"]),
        str(app["uiType"]),
        str(app["os"]),
        str(app["binaryName"]),
        str(app["summary"]),
        " ".join(str(x) for x in app.get("highlights", [])),
        " ".join(str(x) for x in app.get("keywords", [])),
    ]
    return " ".join(part.strip() for part in parts if part and part.strip())


def render_single_card(app: dict[str, Any]) -> str:
    """Render a single software specification card."""
    app_name = esc(app["name"])
    short_name = str(app.get("shortName", "")).strip()
    version = esc(app["version"])
    category = esc(app["category"])
    category_label = esc(app["categoryLabel"])
    ui_type = esc(app["uiType"])
    ui_class = "badge--gui" if app["uiType"] == "GUI" else "badge--cli"
    os_text = esc(app["os"])
    binary_name = esc(app["binaryName"])
    binary_size = esc(app["binarySize"])
    permission_label = esc(app["permissionLabel"])
    summary = esc(app["summary"])
    search_blob = esc(build_search_blob(app))
    repo_url = esc(app["repoUrl"])
    release_url = esc(app["releaseUrl"])
    issues_url = esc(app["issuesUrl"])

    media_html = ""
    screenshot = str(app.get("screenshot", "")).strip()
    if screenshot:
        rel_src = esc(f"./{screenshot.lstrip('./')}")
        alt_text = esc(app.get("screenshotAlt", ""))
        media_html = (
            '\n          <figure class="app-card__media">'
            f'<img src="{rel_src}" alt="{alt_text}" loading="lazy" decoding="async" width="640" height="400">'
            "</figure>"
        )

    subtitle_html = ""
    if short_name and short_name.lower() not in str(app["name"]).lower():
        subtitle_html = f'<span class="app-card__subname">{esc(short_name)}</span>'

    highlights_html = "\n            ".join(
        f"<li>{esc(item)}</li>" for item in app["highlights"]
    )

    dl_aria = esc(f"ダウンロード - {app['name']} の最新リリース（GitHub・新しいタブで開く）")
    repo_aria = esc(f"GitHub - {app['name']} のリポジトリと説明書（新しいタブで開く）")
    issues_aria = esc(f"不具合報告 - {app['name']} のGitHub Issues（新しいタブで開く）")

    return f"""        <article class="app-card" data-category="{category}" data-search="{search_blob}">{media_html}
          <div class="app-card__meta">
            <span class="app-card__category">{category_label}</span>
            <div class="app-card__badges">
              <span class="badge {ui_class}">{ui_type}</span>
              <span class="version-tag">{version}</span>
            </div>
          </div>
          <header class="app-card__header">
            <h3 class="app-card__title">{app_name}</h3>
            {subtitle_html}
          </header>
          <p class="app-card__summary">{summary}</p>
          <ul class="app-card__highlights">
            {highlights_html}
          </ul>
          <dl class="app-card__specs">
            <div class="spec-row">
              <dt>対象OS</dt>
              <dd>{os_text}</dd>
            </div>
            <div class="spec-row">
              <dt>実行ファイル</dt>
              <dd><code class="mono">{binary_name}</code>（{binary_size}）</dd>
            </div>
            <div class="spec-row">
              <dt>実行権限</dt>
              <dd>{permission_label}</dd>
            </div>
          </dl>
          <div class="app-card__actions">
            <a class="btn btn--primary" href="{release_url}" target="_blank" rel="noopener noreferrer" aria-label="{dl_aria}">
              {ICON_DOWNLOAD}
              <span>ダウンロード</span>
            </a>
            <a class="btn btn--secondary" href="{repo_url}" target="_blank" rel="noopener noreferrer" aria-label="{repo_aria}">
              {ICON_EXTERNAL}
              <span>GitHub</span>
            </a>
            <a class="btn btn--ghost" href="{issues_url}" target="_blank" rel="noopener noreferrer" aria-label="{issues_aria}">
              <span>不具合報告</span>
            </a>
          </div>
        </article>"""


def render_apps_html(data: dict[str, Any]) -> str:
    """Render all software cards in deterministic order."""
    cards = [render_single_card(app) for app in sorted_apps(data)]
    return "\n".join(cards)


def replace_marker_block(text: str, marker: str, replacement: str, inline: bool = False) -> str:
    """Replace content between <!-- MARKER:START --> and <!-- MARKER:END -->."""
    pattern = re.compile(
        rf"(<!--\s*{re.escape(marker)}:START\s*-->)(.*?)(<!--\s*{re.escape(marker)}:END\s*-->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError(f"Marker block not found in index.html: {marker}")

    def _repl(match: re.Match[str]) -> str:
        if inline:
            return f"{match.group(1)}{replacement}{match.group(3)}"
        return f"{match.group(1)}\n            {replacement}\n            {match.group(3)}"

    if marker == "APPS":
        def _repl_apps(match: re.Match[str]) -> str:
            return f"{match.group(1)}\n{replacement}\n        {match.group(3)}"

        return pattern.sub(_repl_apps, text, count=1)

    return pattern.sub(_repl, text, count=1)


def sync_html_text(html_text: str, data: dict[str, Any]) -> str:
    """Return synchronized index.html text for the given catalog dictionary."""
    validate_catalog(data)
    updated = replace_marker_block(html_text, "COUNT", str(len(data["apps"])), inline=True)
    updated = replace_marker_block(updated, "FILTERS", render_filters_html(data), inline=False)
    updated = replace_marker_block(updated, "APPS", render_apps_html(data), inline=False)
    return updated


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for synchronizing or verifying index.html."""
    parser = argparse.ArgumentParser(description="Synchronize portal index.html with data/apps.json")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify index.html matches data/apps.json without modifying files",
    )
    args = parser.parse_args(argv)

    root_dir = Path(__file__).resolve().parent.parent
    data_path = root_dir / "data" / "apps.json"
    html_path = root_dir / "index.html"

    catalog = json.loads(data_path.read_text(encoding="utf-8"))
    current_html = html_path.read_text(encoding="utf-8")
    expected_html = sync_html_text(current_html, catalog)

    if args.check:
        if current_html != expected_html:
            print("[NG] index.html is out of sync with data/apps.json. Run scripts/sync_apps.py.")
            return 1
        print(f"[OK] index.html is in sync with data/apps.json ({len(catalog['apps'])} apps).")
        return 0

    html_path.write_text(expected_html, encoding="utf-8", newline="\n")
    print(f"[OK] Updated index.html from data/apps.json ({len(catalog['apps'])} apps).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
