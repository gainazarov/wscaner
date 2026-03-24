"""Diff Engine — compares scan results to find new/removed URLs."""

from typing import NamedTuple


class DiffResult(NamedTuple):
    """Result of comparing two sets of URLs."""
    new_urls: set[str]
    removed_urls: set[str]
    unchanged_urls: set[str]


def compute_diff(current_urls: set[str], previous_urls: set[str]) -> DiffResult:
    """
    Compare current scan URLs with previous scan URLs.
    
    Returns:
        DiffResult with new, removed, and unchanged URL sets.
    """
    new_urls = current_urls - previous_urls
    removed_urls = previous_urls - current_urls
    unchanged_urls = current_urls & previous_urls

    return DiffResult(
        new_urls=new_urls,
        removed_urls=removed_urls,
        unchanged_urls=unchanged_urls,
    )


def format_diff_report(diff: DiffResult) -> str:
    """Generate a human-readable diff report."""
    lines = []
    lines.append(f"=== Scan Diff Report ===")
    lines.append(f"New URLs: {len(diff.new_urls)}")
    lines.append(f"Removed URLs: {len(diff.removed_urls)}")
    lines.append(f"Unchanged: {len(diff.unchanged_urls)}")
    lines.append("")

    if diff.new_urls:
        lines.append("--- New URLs ---")
        for url in sorted(diff.new_urls):
            lines.append(f"  + {url}")
        lines.append("")

    if diff.removed_urls:
        lines.append("--- Removed URLs ---")
        for url in sorted(diff.removed_urls):
            lines.append(f"  - {url}")

    return "\n".join(lines)
