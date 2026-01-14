"""Table output formatting using Rich."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text to max length."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def format_paper_table(papers: list[dict[str, Any]], console: Console | None = None) -> None:
    """Print papers as a table.

    Args:
        papers: List of paper dictionaries.
        console: Rich console instance (creates new one if not provided).
    """
    if console is None:
        console = Console()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Year", justify="right")
    table.add_column("Citations", justify="right")
    table.add_column("Title", max_width=60)
    table.add_column("Authors", max_width=30)

    for paper in papers:
        if not paper:
            continue

        paper_id = paper.get("paperId", "")[:12] if paper.get("paperId") else ""
        year = str(paper.get("year", "")) if paper.get("year") else ""
        citations = str(paper.get("citationCount", "")) if paper.get("citationCount") else ""
        title = _truncate(paper.get("title", ""), 60)

        # Format authors
        authors = paper.get("authors", [])
        if authors:
            if isinstance(authors[0], dict):
                author_names = [a.get("name", "") for a in authors[:3]]
            else:
                author_names = [str(a) for a in authors[:3]]
            authors_str = ", ".join(filter(None, author_names))
            if len(authors) > 3:
                authors_str += f" +{len(authors) - 3}"
        else:
            authors_str = ""

        table.add_row(paper_id, year, citations, title, authors_str)

    console.print(table)


def format_author_table(authors: list[dict[str, Any]], console: Console | None = None) -> None:
    """Print authors as a table.

    Args:
        authors: List of author dictionaries.
        console: Rich console instance.
    """
    if console is None:
        console = Console()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Name", max_width=30)
    table.add_column("Papers", justify="right")
    table.add_column("Citations", justify="right")
    table.add_column("h-index", justify="right")
    table.add_column("Affiliations", max_width=40)

    for author in authors:
        if not author:
            continue

        author_id = author.get("authorId", "")[:12] if author.get("authorId") else ""
        name = _truncate(author.get("name", ""), 30)
        papers = str(author.get("paperCount", "")) if author.get("paperCount") else ""
        citations = str(author.get("citationCount", "")) if author.get("citationCount") else ""
        h_index = str(author.get("hIndex", "")) if author.get("hIndex") else ""

        affiliations = author.get("affiliations", [])
        affiliations_str = ", ".join(affiliations[:2]) if affiliations else ""
        if len(affiliations) > 2:
            affiliations_str += f" +{len(affiliations) - 2}"

        table.add_row(author_id, name, papers, citations, h_index, affiliations_str)

    console.print(table)


def format_citation_table(citations: list[dict[str, Any]], console: Console | None = None) -> None:
    """Print citations as a table.

    Args:
        citations: List of citation objects (with citingPaper/citedPaper).
        console: Rich console instance.
    """
    if console is None:
        console = Console()

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Year", justify="right")
    table.add_column("Citations", justify="right")
    table.add_column("Title", max_width=60)
    table.add_column("Influential", justify="center")

    for item in citations:
        if not item:
            continue

        # Get the actual paper (citingPaper for citations, citedPaper for references)
        paper = item.get("citingPaper") or item.get("citedPaper") or item
        is_influential = item.get("isInfluential", False)

        paper_id = paper.get("paperId", "")[:12] if paper.get("paperId") else ""
        year = str(paper.get("year", "")) if paper.get("year") else ""
        citation_count = str(paper.get("citationCount", "")) if paper.get("citationCount") else ""
        title = _truncate(paper.get("title", ""), 60)
        influential = "[green]Yes[/green]" if is_influential else ""

        table.add_row(paper_id, year, citation_count, title, influential)

    console.print(table)


def format_table_output(
    data: list[dict[str, Any]] | dict[str, Any],
    data_type: str = "paper",
    console: Console | None = None,
) -> None:
    """Format data as a table.

    Args:
        data: Data to format (list or dict with 'data' key).
        data_type: Type of data ('paper', 'author', 'citation').
        console: Rich console instance.
    """
    # Extract list from paginated response
    if isinstance(data, dict):
        items = data.get("data", [])
    else:
        items = data

    if data_type == "author":
        format_author_table(items, console)
    elif data_type == "citation":
        format_citation_table(items, console)
    else:
        format_paper_table(items, console)
