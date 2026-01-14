"""JSON output formatting."""

from __future__ import annotations

import json
import sys
from typing import Any

from s2cli.formatters.bibtex import to_bibtex


def _enrich_paper_with_bibtex(paper: dict[str, Any]) -> dict[str, Any]:
    """Add BibTeX to paper if it has enough data."""
    if paper and paper.get("title") and paper.get("paperId"):
        paper = paper.copy()
        paper["bibtex"] = to_bibtex(paper)
    return paper


def format_json_output(
    data: dict[str, Any] | list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
    include_bibtex: bool = True,
) -> str:
    """Format data as pretty-printed JSON.

    Args:
        data: The data to format (list of papers, single paper, etc.)
        meta: Optional metadata to include (query, pagination, etc.)
        include_bibtex: Whether to add BibTeX to paper results.

    Returns:
        JSON string.
    """
    # Determine if we should pretty-print based on terminal
    indent = 2 if sys.stdout.isatty() else None

    # Handle list of papers (search results, citations, etc.)
    if isinstance(data, list):
        results = data
        if include_bibtex:
            results = [_enrich_paper_with_bibtex(p) if p else p for p in results]

        output = {"results": results}
        if meta:
            output["meta"] = meta

    # Handle dict with 'data' key (API pagination response)
    elif isinstance(data, dict) and "data" in data:
        results = data["data"]
        if include_bibtex:
            # Handle citation/reference format where paper is nested
            enriched = []
            for item in results:
                if item:
                    # Citations have 'citingPaper', references have 'citedPaper'
                    if "citingPaper" in item:
                        item = item.copy()
                        item["citingPaper"] = _enrich_paper_with_bibtex(item["citingPaper"])
                    elif "citedPaper" in item:
                        item = item.copy()
                        item["citedPaper"] = _enrich_paper_with_bibtex(item["citedPaper"])
                    else:
                        item = _enrich_paper_with_bibtex(item)
                enriched.append(item)
            results = enriched

        output = {"results": results}
        # Add pagination info from API response
        pagination = {}
        if "total" in data:
            pagination["total"] = data["total"]
        if "offset" in data:
            pagination["offset"] = data["offset"]
        if "next" in data:
            pagination["next"] = data["next"]
        if pagination:
            if meta:
                meta.update(pagination)
            else:
                meta = pagination
        if meta:
            output["meta"] = meta

    # Handle single paper/author
    elif isinstance(data, dict):
        if include_bibtex and data.get("paperId"):
            data = _enrich_paper_with_bibtex(data)
        output = data

    else:
        output = data

    return json.dumps(output, indent=indent, ensure_ascii=False)
