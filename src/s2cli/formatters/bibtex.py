"""BibTeX formatting utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize_text(text: str) -> str:
    """Normalize unicode text for BibTeX compatibility."""
    # Normalize to NFKD form and encode to ASCII
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _escape_bibtex(text: str) -> str:
    """Escape special characters for BibTeX."""
    if not text:
        return ""
    # Escape special LaTeX characters
    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def _generate_cite_key(paper: dict[str, Any]) -> str:
    """Generate a citation key from paper data.

    Format: firstauthor_year_firstword (e.g., vaswani2017attention)
    """
    # Get first author's last name
    authors = paper.get("authors", [])
    if authors:
        first_author = authors[0]
        if isinstance(first_author, dict):
            name = first_author.get("name", "unknown")
        else:
            name = str(first_author)
        # Extract last name (last word of name)
        last_name = name.split()[-1].lower() if name else "unknown"
        # Remove non-alphanumeric characters
        last_name = re.sub(r"[^a-z]", "", _normalize_text(last_name))
    else:
        last_name = "unknown"

    # Get year
    year = paper.get("year", "")
    if not year:
        year = "nodate"

    # Get first significant word from title
    title = paper.get("title", "")
    if title:
        # Remove common words and get first significant word
        stopwords = {"a", "an", "the", "on", "in", "of", "for", "and", "or", "to", "with"}
        words = re.findall(r"\b[a-zA-Z]+\b", _normalize_text(title.lower()))
        title_word = next((w for w in words if w not in stopwords), "paper")
    else:
        title_word = "paper"

    return f"{last_name}{year}{title_word}"


def _get_entry_type(paper: dict[str, Any]) -> str:
    """Determine the BibTeX entry type based on paper data."""
    # Check publication venue for hints
    venue = paper.get("publicationVenue", {}) or {}
    venue_type = venue.get("type", "") if isinstance(venue, dict) else ""

    if venue_type == "conference":
        return "inproceedings"
    elif venue_type == "journal":
        return "article"

    # Check venue name for hints
    venue_name = (paper.get("venue", "") or "").lower()
    if any(kw in venue_name for kw in ["conference", "proceedings", "workshop", "symposium"]):
        return "inproceedings"
    elif any(kw in venue_name for kw in ["journal", "transactions", "review"]):
        return "article"

    # Check external IDs
    external_ids = paper.get("externalIds", {}) or {}
    if external_ids.get("ArXiv"):
        return "article"  # arXiv papers are typically articles

    # Default to article
    return "article"


def to_bibtex(paper: dict[str, Any]) -> str:
    """Convert a paper dict to BibTeX format.

    Args:
        paper: Paper data dictionary from S2 API.

    Returns:
        BibTeX string for the paper.
    """
    cite_key = _generate_cite_key(paper)
    entry_type = _get_entry_type(paper)

    # Build author string
    authors = paper.get("authors", [])
    if authors:
        author_names = []
        for author in authors:
            if isinstance(author, dict):
                author_names.append(author.get("name", ""))
            else:
                author_names.append(str(author))
        author_str = " and ".join(filter(None, author_names))
    else:
        author_str = ""

    # Get external IDs
    external_ids = paper.get("externalIds", {}) or {}

    # Build BibTeX fields
    fields = []

    title = paper.get("title", "")
    if title:
        fields.append(f"  title = {{{_escape_bibtex(title)}}}")

    if author_str:
        fields.append(f"  author = {{{_escape_bibtex(author_str)}}}")

    year = paper.get("year")
    if year:
        fields.append(f"  year = {{{year}}}")

    # Venue/journal/booktitle depending on entry type
    venue = paper.get("venue", "")
    if venue:
        if entry_type == "inproceedings":
            fields.append(f"  booktitle = {{{_escape_bibtex(venue)}}}")
        else:
            fields.append(f"  journal = {{{_escape_bibtex(venue)}}}")

    # DOI
    doi = external_ids.get("DOI")
    if doi:
        fields.append(f"  doi = {{{doi}}}")

    # arXiv ID
    arxiv_id = external_ids.get("ArXiv")
    if arxiv_id:
        fields.append(f"  eprint = {{{arxiv_id}}}")
        fields.append("  archiveprefix = {arXiv}")

    # URL (open access PDF or S2 URL)
    open_access = paper.get("openAccessPdf", {})
    if open_access and isinstance(open_access, dict):
        url = open_access.get("url")
        if url:
            fields.append(f"  url = {{{url}}}")
    elif paper.get("paperId"):
        fields.append(f"  url = {{https://www.semanticscholar.org/paper/{paper['paperId']}}}")

    # Abstract (optional, can be large)
    abstract = paper.get("abstract", "")
    if abstract:
        # Truncate very long abstracts
        if len(abstract) > 1000:
            abstract = abstract[:997] + "..."
        fields.append(f"  abstract = {{{_escape_bibtex(abstract)}}}")

    # Assemble the entry
    fields_str = ",\n".join(fields)
    return f"@{entry_type}{{{cite_key},\n{fields_str}\n}}"


def format_bibtex_output(papers: list[dict[str, Any]]) -> str:
    """Format multiple papers as BibTeX.

    Args:
        papers: List of paper dictionaries.

    Returns:
        BibTeX string with all papers.
    """
    entries = []
    for paper in papers:
        if paper:  # Skip None entries (from batch that returned null)
            entries.append(to_bibtex(paper))
    return "\n\n".join(entries)
