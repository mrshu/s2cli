"""Semantic Scholar API client."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

# API base URLs
GRAPH_API_BASE = "https://api.semanticscholar.org/graph/v1"
RECOMMENDATIONS_API_BASE = "https://api.semanticscholar.org/recommendations/v1"
DATASETS_API_BASE = "https://api.semanticscholar.org/datasets/v1"

# Default fields for different endpoints
DEFAULT_PAPER_FIELDS = "paperId,title,year,authors,citationCount,abstract,venue,openAccessPdf,externalIds"
DEFAULT_AUTHOR_FIELDS = "authorId,name,affiliations,paperCount,citationCount,hIndex"
BIBTEX_FIELDS = "paperId,title,year,authors,venue,externalIds,journal,publicationVenue"


class APIError(Exception):
    """API error with structured information."""

    def __init__(
        self,
        code: str,
        message: str,
        suggestion: str | None = None,
        status_code: int | None = None,
    ):
        self.code = code
        self.message = message
        self.suggestion = suggestion
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.suggestion:
            result["error"]["suggestion"] = self.suggestion
        if self.status_code:
            result["error"]["status_code"] = self.status_code
        result["error"]["documentation"] = "https://api.semanticscholar.org/api-docs/"
        return result


class SemanticScholarAPI:
    """Client for Semantic Scholar API."""

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        """Initialize the API client.

        Args:
            api_key: Optional API key for higher rate limits.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or os.environ.get("S2_API_KEY")
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if self._client is None:
            headers = {"User-Agent": "s2cli/0.1.0"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._client = httpx.Client(headers=headers, timeout=self.timeout)
        return self._client

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate errors."""
        if response.status_code == 200:
            return response.json()

        # Handle specific error codes
        if response.status_code == 404:
            raise APIError(
                code="NOT_FOUND",
                message="Resource not found",
                suggestion="Check the ID format or try searching instead",
                status_code=404,
            )
        elif response.status_code == 400:
            try:
                error_data = response.json()
                message = error_data.get("message", "Bad request")
            except Exception:
                message = "Bad request"
            raise APIError(
                code="BAD_REQUEST",
                message=message,
                suggestion="Check query parameters and field names",
                status_code=400,
            )
        elif response.status_code == 429:
            raise APIError(
                code="RATE_LIMITED",
                message="Rate limit exceeded",
                suggestion="Wait a moment or use an API key for higher limits",
                status_code=429,
            )
        else:
            raise APIError(
                code="API_ERROR",
                message=f"API returned status {response.status_code}",
                status_code=response.status_code,
            )

    # Paper endpoints

    def search_papers(
        self,
        query: str,
        fields: str | None = None,
        limit: int = 10,
        offset: int = 0,
        year: str | None = None,
        venue: str | None = None,
        fields_of_study: str | None = None,
        min_citation_count: int | None = None,
        open_access_pdf: bool = False,
        publication_types: str | None = None,
    ) -> dict[str, Any]:
        """Search for papers by keyword."""
        params: dict[str, Any] = {
            "query": query,
            "fields": fields or DEFAULT_PAPER_FIELDS,
            "limit": min(limit, 100),  # API max is 100
            "offset": offset,
        }

        if year:
            params["year"] = year
        if venue:
            params["venue"] = venue
        if fields_of_study:
            params["fieldsOfStudy"] = fields_of_study
        if min_citation_count is not None:
            params["minCitationCount"] = min_citation_count
        if open_access_pdf:
            params["openAccessPdf"] = ""
        if publication_types:
            params["publicationTypes"] = publication_types

        response = self.client.get(f"{GRAPH_API_BASE}/paper/search", params=params)
        return self._handle_response(response)

    def get_paper(self, paper_id: str, fields: str | None = None) -> dict[str, Any]:
        """Get details for a single paper."""
        params = {"fields": fields or DEFAULT_PAPER_FIELDS}
        # URL-encode the paper_id to handle DOIs with slashes
        encoded_id = quote(paper_id, safe=":")
        response = self.client.get(f"{GRAPH_API_BASE}/paper/{encoded_id}", params=params)
        return self._handle_response(response)

    def get_papers_batch(
        self, paper_ids: list[str], fields: str | None = None
    ) -> list[dict[str, Any]]:
        """Get details for multiple papers (batch endpoint)."""
        params = {"fields": fields or DEFAULT_PAPER_FIELDS}
        response = self.client.post(
            f"{GRAPH_API_BASE}/paper/batch",
            params=params,
            json={"ids": paper_ids[:500]},  # API max is 500
        )
        return self._handle_response(response)

    def get_paper_citations(
        self,
        paper_id: str,
        fields: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get papers citing this paper."""
        params = {
            "fields": fields or DEFAULT_PAPER_FIELDS,
            "limit": min(limit, 1000),
            "offset": offset,
        }
        encoded_id = quote(paper_id, safe=":")
        response = self.client.get(
            f"{GRAPH_API_BASE}/paper/{encoded_id}/citations", params=params
        )
        return self._handle_response(response)

    def get_paper_references(
        self,
        paper_id: str,
        fields: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get papers cited by this paper."""
        params = {
            "fields": fields or DEFAULT_PAPER_FIELDS,
            "limit": min(limit, 1000),
            "offset": offset,
        }
        encoded_id = quote(paper_id, safe=":")
        response = self.client.get(
            f"{GRAPH_API_BASE}/paper/{encoded_id}/references", params=params
        )
        return self._handle_response(response)

    # Author endpoints

    def search_authors(
        self,
        query: str,
        fields: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search for authors by name."""
        params = {
            "query": query,
            "fields": fields or DEFAULT_AUTHOR_FIELDS,
            "limit": min(limit, 1000),
            "offset": offset,
        }
        response = self.client.get(f"{GRAPH_API_BASE}/author/search", params=params)
        return self._handle_response(response)

    def get_author(self, author_id: str, fields: str | None = None) -> dict[str, Any]:
        """Get details for a single author."""
        params = {"fields": fields or DEFAULT_AUTHOR_FIELDS}
        response = self.client.get(f"{GRAPH_API_BASE}/author/{author_id}", params=params)
        return self._handle_response(response)

    def get_author_papers(
        self,
        author_id: str,
        fields: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get papers by an author."""
        params = {
            "fields": fields or DEFAULT_PAPER_FIELDS,
            "limit": min(limit, 1000),
            "offset": offset,
        }
        response = self.client.get(
            f"{GRAPH_API_BASE}/author/{author_id}/papers", params=params
        )
        return self._handle_response(response)

    # Recommendations endpoint

    def get_recommendations(
        self,
        paper_id: str,
        fields: str | None = None,
        limit: int = 10,
        pool: str = "recent",
    ) -> dict[str, Any]:
        """Get paper recommendations for a single paper."""
        params = {
            "fields": fields or DEFAULT_PAPER_FIELDS,
            "limit": min(limit, 500),
            "from": pool,
        }
        encoded_id = quote(paper_id, safe=":")
        response = self.client.get(
            f"{RECOMMENDATIONS_API_BASE}/papers/forpaper/{encoded_id}", params=params
        )
        return self._handle_response(response)

    def get_recommendations_multi(
        self,
        positive_paper_ids: list[str],
        negative_paper_ids: list[str] | None = None,
        fields: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get recommendations based on positive/negative examples."""
        params = {
            "fields": fields or DEFAULT_PAPER_FIELDS,
            "limit": min(limit, 500),
        }
        payload = {
            "positivePaperIds": positive_paper_ids,
        }
        if negative_paper_ids:
            payload["negativePaperIds"] = negative_paper_ids

        response = self.client.post(
            f"{RECOMMENDATIONS_API_BASE}/papers/",
            params=params,
            json=payload,
        )
        return self._handle_response(response)

    # Dataset endpoints

    def list_releases(self) -> list[str]:
        """List available dataset releases."""
        response = self.client.get(f"{DATASETS_API_BASE}/release/")
        return self._handle_response(response)

    def get_release(self, release_id: str) -> dict[str, Any]:
        """Get datasets in a release."""
        response = self.client.get(f"{DATASETS_API_BASE}/release/{release_id}")
        return self._handle_response(response)

    def get_dataset_links(self, release_id: str, dataset_name: str) -> dict[str, Any]:
        """Get download links for a dataset."""
        response = self.client.get(
            f"{DATASETS_API_BASE}/release/{release_id}/dataset/{dataset_name}"
        )
        return self._handle_response(response)

    def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
