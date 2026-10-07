"""Decoy page generators and API payload handlers."""

from __future__ import annotations

import html
from typing import Any

from sb.offense.honeypots import get_configured_trap_paths


def decoy_index_html(title: str = "System Documentation") -> str:
    """Generate a synthetic neutral system documentation index page.

    Includes navigation links to configured trap paths or generic documentation sections.
    """
    escaped_title = html.escape(title)
    configured_paths = get_configured_trap_paths()
    if configured_paths:
        links_html = "\n".join(
            f'        <li><a href="{html.escape(p)}">{html.escape(p.strip("/").replace("/", " ").title() or "Section")}</a></li>'
            for p in configured_paths
        )
    else:
        links_html = (
            '        <li><a href="/docs/architecture">Architecture Guide</a></li>\n'
            '        <li><a href="/docs/api">API Reference</a></li>\n'
            '        <li><a href="/docs/team">Team Directory</a></li>\n'
            '        <li><a href="/docs/operations">Operations Handbook</a></li>\n'
            '        <li><a href="/docs/metrics">Key Metrics</a></li>'
        )

    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        f"<head><title>{escaped_title}</title></head>\n"
        "<body>\n"
        '<main id="content">\n'
        f"    <h1>{escaped_title}</h1>\n"
        "    <p>Internal engineering documentation and technical resource directory.</p>\n"
        "    <ul>\n"
        f"{links_html}\n"
        "    </ul>\n"
        "</main>\n"
        "</body>\n"
        "</html>"
    )


def decoy_api_payload(canary: Any) -> dict[str, Any]:
    """Return neutral JSON payload for the decoy API carrying canary content."""
    notes = getattr(canary, "canonical_content", None) or getattr(canary, "value", "") or str(canary)
    return {
        "service": "system-reconcile",
        "version": "v1",
        "status": "deprecated",
        "notes": notes,
    }
