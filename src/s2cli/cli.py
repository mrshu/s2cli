"""Main CLI application for s2cli."""

from __future__ import annotations

import json
import sys
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


def get_api(
    api_key: str | None = None,
    no_retry: bool = False,
) -> SemanticScholarAPI:
    """Get API client instance."""
    return SemanticScholarAPI(
        api_key=api_key,
        retry_enabled=not no_retry,
    )


def is_interactive() -> bool:
    """Check if stdout is connected to a terminal (not piped)."""
    return sys.stdout.isatty()


def output_results(
    data: dict | list,
    meta: dict | None = None,
    data_type: str = "paper",
    use_json: bool = False,
    use_bibtex: bool = False,
    include_bibtex_in_json: bool = True,
):
    """Output results in the appropriate format.

    Format selection logic:
    1. If --json flag is set: JSON output
    2. If --bibtex flag is set: BibTeX output
    3. If stdout is a terminal: human-readable table
    4. If stdout is piped: compact JSON (for scripts/agents)
    """
    if use_bibtex:
        # BibTeX output
        if isinstance(data, dict) and "data" in data:
            papers = data["data"]
        elif isinstance(data, dict) and "recommendedPapers" in data:
            papers = data["recommendedPapers"]
        elif isinstance(data, list):
            papers = data
        else:
            papers = [data]

        # Handle citation/reference format
        extracted = []
        for item in papers:
            if item:
                if "citingPaper" in item:
                    extracted.append(item["citingPaper"])
                elif "citedPaper" in item:
                    extracted.append(item["citedPaper"])
                else:
                    extracted.append(item)
        print(format_bibtex_output(extracted))

    elif use_json or not is_interactive():
        # JSON output (explicit --json or piped)
        output = format_json_output(data, meta=meta, include_bibtex=include_bibtex_in_json)
        # Compact JSON when piped, pretty when explicit --json in terminal
        if not is_interactive() and not use_json:
            # Re-format as compact JSON for piping
            try:
                parsed = json.loads(output)
                output = json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        print(output)

    else:
        # Human-readable table (terminal default)
        format_table_output(data, data_type=data_type, console=console)

        # Show pagination info
        if isinstance(data, dict):
            total = data.get("total")
            if total:
                console.print(f"\n[dim]Showing {len(data.get('data', []))} of {total} results[/dim]")


def output_error(e: APIError):
    """Output error in appropriate format."""
    error_data = e.to_dict()
    if is_interactive():
        console.print(f"[red]Error:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[dim]{e.suggestion}[/dim]")
    else:
        print(json.dumps(error_data, ensure_ascii=False))
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
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    bibtex_output: Annotated[bool, typer.Option("--bibtex", "-b", help="Output as BibTeX")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Search for papers by keyword.

    Examples:
        s2cli search "attention mechanism"
        s2cli search "transformers" --year 2020-2024 --min-citations 100
        s2cli search "BERT" --json | jq '.results[0]'
    """
    api = get_api(api_key, no_retry=no_retry)
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
            meta["next"] = f"s2cli search '{query}' --offset {offset + limit}"

        output_results(result, meta=meta, data_type="paper", use_json=json_output, use_bibtex=bibtex_output)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@app.command()
def paper(
    paper_ids: Annotated[list[str], typer.Argument(help="Paper ID(s) - S2 ID, DOI, arXiv ID, etc.")],
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    bibtex_output: Annotated[bool, typer.Option("--bibtex", "-b", help="Output as BibTeX")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get paper details by ID.

    Supports multiple ID formats:
        Semantic Scholar: 649def34f8be52c8b66281af98ae884c09aef38b
        DOI: DOI:10.18653/v1/N18-3011
        arXiv: ARXIV:2106.15928
        CorpusId: CorpusId:215416146

    Examples:
        s2cli paper ARXIV:1706.03762
        s2cli paper DOI:10.18653/v1/N18-3011 --bibtex
    """
    api = get_api(api_key, no_retry=no_retry)
    try:
        if len(paper_ids) == 1:
            result = api.get_paper(paper_ids[0], fields=fields)
            papers = [result]
        else:
            papers = api.get_papers_batch(paper_ids, fields=fields)

        output_results(papers, data_type="paper", use_json=json_output, use_bibtex=bibtex_output)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@app.command()
def citations(
    paper_id: Annotated[str, typer.Argument(help="Paper ID")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    bibtex_output: Annotated[bool, typer.Option("--bibtex", "-b", help="Output as BibTeX")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get papers that cite this paper."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.get_paper_citations(paper_id, fields=fields, limit=limit, offset=offset)
        meta = {"paper_id": paper_id, "type": "citations", "limit": limit, "offset": offset}
        output_results(result, meta=meta, data_type="citation", use_json=json_output, use_bibtex=bibtex_output)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@app.command()
def references(
    paper_id: Annotated[str, typer.Argument(help="Paper ID")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    bibtex_output: Annotated[bool, typer.Option("--bibtex", "-b", help="Output as BibTeX")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get papers cited by this paper."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.get_paper_references(paper_id, fields=fields, limit=limit, offset=offset)
        meta = {"paper_id": paper_id, "type": "references", "limit": limit, "offset": offset}
        output_results(result, meta=meta, data_type="citation", use_json=json_output, use_bibtex=bibtex_output)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@app.command()
def recommend(
    paper_id: Annotated[str, typer.Argument(help="Paper ID to get recommendations for")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of recommendations")] = 10,
    pool: Annotated[str, typer.Option("--pool", help="Pool: 'recent' or 'all-cs'")] = "recent",
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    bibtex_output: Annotated[bool, typer.Option("--bibtex", "-b", help="Output as BibTeX")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get paper recommendations based on a seed paper."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.get_recommendations(paper_id, fields=fields, limit=limit, pool=pool)
        papers = result.get("recommendedPapers", [])
        meta = {"paper_id": paper_id, "type": "recommendations", "pool": pool, "limit": limit}
        output_results(papers, meta=meta, data_type="paper", use_json=json_output, use_bibtex=bibtex_output)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@app.command()
def bibtex(
    paper_ids: Annotated[list[str], typer.Argument(help="Paper ID(s)")],
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Export BibTeX citations for papers.

    Shortcut for: s2cli paper <ids> --bibtex
    """
    api = get_api(api_key, no_retry=no_retry)
    try:
        bibtex_fields = "paperId,title,year,authors,venue,externalIds,journal,publicationVenue,abstract,openAccessPdf"

        if len(paper_ids) == 1:
            result = api.get_paper(paper_ids[0], fields=bibtex_fields)
            papers = [result]
        else:
            papers = api.get_papers_batch(paper_ids, fields=bibtex_fields)

        print(format_bibtex_output(papers))

    except APIError as e:
        output_error(e)
    finally:
        api.close()


# === Author Commands ===


@author_app.command("get")
def author_get(
    author_id: Annotated[str, typer.Argument(help="Author ID")],
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get author details by ID."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.get_author(author_id, fields=fields)
        output_results([result], data_type="author", use_json=json_output, include_bibtex_in_json=False)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@author_app.command("search")
def author_search(
    query: Annotated[str, typer.Argument(help="Author name to search")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Search for authors by name."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.search_authors(query, fields=fields, limit=limit, offset=offset)
        meta = {"query": query, "limit": limit, "offset": offset}
        if result.get("total"):
            meta["total"] = result["total"]
        output_results(result, meta=meta, data_type="author", use_json=json_output, include_bibtex_in_json=False)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@author_app.command("papers")
def author_papers(
    author_id: Annotated[str, typer.Argument(help="Author ID")],
    limit: Annotated[int, typer.Option("-n", "--limit", help="Number of results")] = 10,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset")] = 0,
    fields: Annotated[Optional[str], typer.Option("--fields", help="API fields to return")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    bibtex_output: Annotated[bool, typer.Option("--bibtex", "-b", help="Output as BibTeX")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get papers by an author."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.get_author_papers(author_id, fields=fields, limit=limit, offset=offset)
        meta = {"author_id": author_id, "limit": limit, "offset": offset}
        output_results(result, meta=meta, data_type="paper", use_json=json_output, use_bibtex=bibtex_output)

    except APIError as e:
        output_error(e)
    finally:
        api.close()


# === Dataset Commands ===


@app.command()
def datasets(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """List available dataset releases."""
    api = get_api(api_key, no_retry=no_retry)
    try:
        result = api.list_releases()
        if json_output or not is_interactive():
            print(json.dumps(result, ensure_ascii=False, indent=2 if is_interactive() else None))
        else:
            console.print("[bold]Available Dataset Releases:[/bold]\n")
            for release in result[:20]:  # Show latest 20
                console.print(f"  {release}")
            if len(result) > 20:
                console.print(f"\n[dim]... and {len(result) - 20} more[/dim]")

    except APIError as e:
        output_error(e)
    finally:
        api.close()


@app.command()
def dataset(
    release_id: Annotated[str, typer.Argument(help="Release ID (e.g., '2024-01-01' or 'latest')")],
    name: Annotated[Optional[str], typer.Option("--name", help="Dataset name for download links")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_retry: Annotated[bool, typer.Option("--no-retry", help="Fail immediately on rate limit")] = False,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="S2_API_KEY", help="API key")] = None,
):
    """Get dataset info or download links.

    Without --name: shows datasets in the release.
    With --name: shows download links for that dataset.
    """
    api = get_api(api_key, no_retry=no_retry)
    try:
        if name:
            result = api.get_dataset_links(release_id, name)
        else:
            result = api.get_release(release_id)

        if json_output or not is_interactive():
            print(json.dumps(result, ensure_ascii=False, indent=2 if is_interactive() else None))
        else:
            print(format_json_output(result, include_bibtex=False))

    except APIError as e:
        output_error(e)
    finally:
        api.close()


if __name__ == "__main__":
    app()
