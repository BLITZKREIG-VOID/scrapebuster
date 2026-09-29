"""Decoy page generators and API payload handlers."""

from __future__ import annotations

import html

from sb.contracts import Canary

INTERNAL_INDEX_PATHS: tuple[str, ...] = (
    "/internal/",
    "/docs/archive/legacy-index",
)


def decoy_index_html(title: str = "CampusCart Internal Marketplace Documentation") -> str:
    """Generate a synthetic CampusCart internal marketplace docs index page.

    Contains navigation links to the 5 documentation sections without
    containing any canary anchors or canary text.
    """
    escaped_title = html.escape(title)
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        f"<head><title>{escaped_title}</title></head>\n"
        "<body>\n"
        '<main id="content">\n'
        f"    <h1>{escaped_title}</h1>\n"
        "    <p>Internal engineering documentation and technical resource directory.</p>\n"
        "    <ul>\n"
        '        <li><a href="/docs/architecture">Architecture Guide</a> - '
        "Overview of system components, backend microservices, and network topologies.</li>\n"
        '        <li><a href="/docs/api">API Reference</a> - '
        "Public and partner developer interface specifications, endpoints, and authentication schemes.</li>\n"
        '        <li><a href="/docs/team">Team Directory</a> - '
        "Directory of engineering groups, leadership contacts, and office locations.</li>\n"
        '        <li><a href="/docs/operations">Operations Handbook</a> - '
        "Runbooks, standard operating procedures, escalation policies, and deployment guidelines.</li>\n"
        '        <li><a href="/docs/metrics">Key Metrics</a> - '
        "Service level objectives, platform availability benchmarks, and annual performance data.</li>\n"
        "    </ul>\n"
        "</main>\n"
        "</body>\n"
        "</html>"
    )


def decoy_api_payload(canary: Canary) -> dict:
    """Return JSON payload for the decoy API carrying canary content."""
    return {
        "service": "campuscart-reconcile",
        "version": "v3",
        "status": "deprecated",
        "notes": canary.canonical_content,
    }
