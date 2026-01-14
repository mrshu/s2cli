"""Main CLI application for s2cli."""

from __future__ import annotations

import sys
from enum import Enum
from typing import Annotated, Optional

import typer
from rich.console import Console

from s2cli.api.client import APIError, SemanticScholarAPI
from s2cli.formatters import format_bibtex_output, format_json_output
from s2cli.formatters.table import format_table_output

app = typer.Typer(
    name="s2cli",
    help="Semantic Scholar CLI - Search academic papers, get citations, export BibTeX.",
    no_args_is_help=True,
)

author_app = typer.Typer(help="Author-related commands")
app.add_typer(author_app, name="author")

console = Console()


class OutputFormat(str, Enum):
    json = "json"
    table = "table"
    bibtex = "bibtex"


def get_api(api_key: str | None = None) -> SemanticScholarAPI:
    """Get API client instance."""
    return SemanticScholarAPI(api_key=api_key)


def handle_error(e: APIError):
    """Handle API errors with appropriate output."""
    error_output = format_json_output(e.to_dict(), include_bibtex=False)
    console.print(error_output, style="red")
    raise typer.Exit(1)


# === Paper Commands ===


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    year: Annotated[Optional[str], typer.Option("--year", help="Year or range (2023, 2020-2023)")] = None,
    venue: Annotated[Optional[str], typer.Option("--venue", help="Filter by venue")] = None,
    field: Annotated[Optional[str], typer.Option("--field", help="Field of study filter")] = None,
    min_citations: Annotated[Optional[int], typer.Option("--min-citations", help="Minimum citation count")] = None,
    open_access: Annotated[bool, typer.Option("--open-access", help="Only papers with free PDFs")] = False,
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields to return")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Search for papers by keyword."""
    api = get_api(api_key)
    try:
        result = api.search_papers(
            query=query,
            fields=fields,
            limit=limit,
            offset=offset,
            year=year,
            venue=venue,
            fields_of_study=field,
            min_citation_count=min_citations,
            open_access_pdf=open_access,
        )

        meta = {"query": query, "limit": limit, "offset": offset}
        if result.get("total"):
            meta["total"] = result["total"]
        if offset + limit < result.get("total", 0):
            meta["next"] = f"s2cli search '{query}' --offset {offset + limit} --limit {limit}"

        if format == OutputFormat.table:
            format_table_output(result, data_type="paper", console=console)
            if result.get("total"):
                console.print(f"\n[dim]Total: {result['total']} results[/dim]")
        elif format == OutputFormat.bibtex:
            papers = result.get("data", [])
            print(format_bibtex_output(papers))
        else:
            print(format_json_output(result, meta=meta))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@app.command()
def paper(
    paper_ids: Annotated[list[str], typer.Argument(help="Paper ID(s) - S2 ID, DOI, arXiv ID, etc.")],
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get paper details by ID.

    Supports multiple ID formats:
    - Semantic Scholar ID: 649def34f8be52c8b66281af98ae884c09aef38b
    - DOI: DOI:10.18653/v1/N18-3011 or 10.18653/v1/N18-3011
    - arXiv: ARXIV:2106.15928 or arXiv:2106.15928
    - CorpusId: CorpusId:215416146
    - URL: https://www.semanticscholar.org/paper/...
    """
    api = get_api(api_key)
    try:
        if len(paper_ids) == 1:
            result = api.get_paper(paper_ids[0], fields=fields)
            papers = [result]
        else:
            # Use batch endpoint for multiple papers
            papers = api.get_papers_batch(paper_ids, fields=fields)

        if format == OutputFormat.table:
            format_table_output(papers, data_type="paper", console=console)
        elif format == OutputFormat.bibtex:
            print(format_bibtex_output(papers))
        else:
            if len(papers) == 1:
                print(format_json_output(papers[0]))
            else:
                print(format_json_output(papers))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@app.command()
def citations(
    paper_id: Annotated[str, typer.Argument(help="Paper ID")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get papers that cite this paper."""
    api = get_api(api_key)
    try:
        result = api.get_paper_citations(paper_id, fields=fields, limit=limit, offset=offset)

        meta = {"paper_id": paper_id, "type": "citations", "limit": limit, "offset": offset}

        if format == OutputFormat.table:
            format_table_output(result, data_type="citation", console=console)
        elif format == OutputFormat.bibtex:
            papers = [item.get("citingPaper") for item in result.get("data", []) if item]
            print(format_bibtex_output(papers))
        else:
            print(format_json_output(result, meta=meta))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@app.command()
def references(
    paper_id: Annotated[str, typer.Argument(help="Paper ID")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get papers cited by this paper."""
    api = get_api(api_key)
    try:
        result = api.get_paper_references(paper_id, fields=fields, limit=limit, offset=offset)

        meta = {"paper_id": paper_id, "type": "references", "limit": limit, "offset": offset}

        if format == OutputFormat.table:
            format_table_output(result, data_type="citation", console=console)
        elif format == OutputFormat.bibtex:
            papers = [item.get("citedPaper") for item in result.get("data", []) if item]
            print(format_bibtex_output(papers))
        else:
            print(format_json_output(result, meta=meta))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@app.command()
def recommend(
    paper_id: Annotated[str, typer.Argument(help="Paper ID to get recommendations for")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of recommendations")] = 10,
    pool: Annotated[str, typer.Option("--pool", help="Recommendation pool: 'recent' or 'all-cs'")] = "recent",
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get paper recommendations based on a seed paper."""
    api = get_api(api_key)
    try:
        result = api.get_recommendations(paper_id, fields=fields, limit=limit, pool=pool)

        meta = {"paper_id": paper_id, "type": "recommendations", "pool": pool, "limit": limit}

        papers = result.get("recommendedPapers", [])

        if format == OutputFormat.table:
            format_table_output(papers, data_type="paper", console=console)
        elif format == OutputFormat.bibtex:
            print(format_bibtex_output(papers))
        else:
            print(format_json_output(papers, meta=meta))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@app.command()
def bibtex(
    paper_ids: Annotated[list[str], typer.Argument(help="Paper ID(s)")],
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Export BibTeX citations for papers.

    This is a shortcut for: s2cli paper <ids> --format bibtex
    """
    api = get_api(api_key)
    try:
        # Use fields optimized for BibTeX
        bibtex_fields = "paperId,title,year,authors,venue,externalIds,journal,publicationVenue,abstract,openAccessPdf"

        if len(paper_ids) == 1:
            result = api.get_paper(paper_ids[0], fields=bibtex_fields)
            papers = [result]
        else:
            papers = api.get_papers_batch(paper_ids, fields=bibtex_fields)

        print(format_bibtex_output(papers))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


# === Author Commands ===


@author_app.command("get")
def author_get(
    author_id: Annotated[str, typer.Argument(help="Author ID")],
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get author details by ID."""
    api = get_api(api_key)
    try:
        result = api.get_author(author_id, fields=fields)

        if format == OutputFormat.table:
            format_table_output([result], data_type="author", console=console)
        else:
            print(format_json_output(result, include_bibtex=False))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@author_app.command("search")
def author_search(
    query: Annotated[str, typer.Argument(help="Author name to search")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Search for authors by name."""
    api = get_api(api_key)
    try:
        result = api.search_authors(query, fields=fields, limit=limit, offset=offset)

        meta = {"query": query, "limit": limit, "offset": offset}
        if result.get("total"):
            meta["total"] = result["total"]

        if format == OutputFormat.table:
            format_table_output(result, data_type="author", console=console)
            if result.get("total"):
                console.print(f"\n[dim]Total: {result['total']} results[/dim]")
        else:
            print(format_json_output(result, meta=meta, include_bibtex=False))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@author_app.command("papers")
def author_papers(
    author_id: Annotated[str, typer.Argument(help="Author ID")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="Comma-separated fields")] = None,
    format: Annotated[OutputFormat, typer.Option("-f", "--format", help="Output format")] = OutputFormat.json,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get papers by an author."""
    api = get_api(api_key)
    try:
        result = api.get_author_papers(author_id, fields=fields, limit=limit, offset=offset)

        meta = {"author_id": author_id, "limit": limit, "offset": offset}

        if format == OutputFormat.table:
            format_table_output(result, data_type="paper", console=console)
        elif format == OutputFormat.bibtex:
            papers = result.get("data", [])
            print(format_bibtex_output(papers))
        else:
            print(format_json_output(result, meta=meta))

    except APIError as e:
        handle_error(e)
    finally:
        api.close()


# === Dataset Commands ===


@app.command()
def datasets(
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """List available dataset releases."""
    api = get_api(api_key)
    try:
        result = api.list_releases()
        print(format_json_output(result, include_bibtex=False))
    except APIError as e:
        handle_error(e)
    finally:
        api.close()


@app.command()
def dataset(
    release_id: Annotated[str, typer.Argument(help="Release ID (e.g., '2024-01-01' or 'latest')")],
    name: Annotated[Optional[str], typer.Option("--name", help="Dataset name for download links")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get dataset info or download links.

    Without --name: shows datasets in the release.
    With --name: shows download links for that dataset.
    """
    api = get_api(api_key)
    try:
        if name:
            result = api.get_dataset_links(release_id, name)
        else:
            result = api.get_release(release_id)
        print(format_json_output(result, include_bibtex=False))
    except APIError as e:
        handle_error(e)
    finally:
        api.close()


if __name__ == "__main__":
    app()
