"""Semantic Scholar API client with retry support."""

from __future__ import annotations

import os
import random
import sys
import time
from typing import Any, Callable
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

# Retry defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_RETRY_WAIT = 60  # seconds
DEFAULT_BASE_DELAY = 1.0  # seconds


class APIError(Exception):
    """API error with structured information."""

    def __init__(
        self,
        code: str,
        message: str,
        suggestion: str | None = None,
        status_code: int | None = None,
        retry_after: int | None = None,
    ):
        self.code = code
        self.message = message
        self.suggestion = suggestion
        self.status_code = status_code
        self.retry_after = retry_after
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
        if self.retry_after:
            result["error"]["retry_after"] = self.retry_after
        result["error"]["documentation"] = "https://api.semanticscholar.org/api-docs/"
        return result


class RateLimitError(APIError):
    """Specific error for rate limiting - can be retried."""

    def __init__(self, retry_after: int | None = None):
        super().__init__(
            code="RATE_LIMITED",
            message="Rate limit exceeded",
            suggestion="Wait a moment or use an API key for higher limits",
            status_code=429,
            retry_after=retry_after,
        )


def _parse_retry_after(response: httpx.Response) -> int | None:
    """Parse Retry-After header, returns seconds to wait."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return int(retry_after)
        except ValueError:
            pass
    return None


def _default_status_callback(message: str) -> None:
    """Default status callback - prints to stderr."""
    if sys.stderr.isatty():
        print(f"\r{message}", end="", file=sys.stderr, flush=True)
    else:
        print(message, file=sys.stderr)


def _default_status_clear() -> None:
    """Clear status line."""
    if sys.stderr.isatty():
        print("\r" + " " * 60 + "\r", end="", file=sys.stderr, flush=True)


class SemanticScholarAPI:
    """Client for Semantic Scholar API with automatic retry."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_retry_wait: int = DEFAULT_MAX_RETRY_WAIT,
        retry_enabled: bool = True,
        status_callback: Callable[[str], None] | None = None,
    ):
        """Initialize the API client.

        Args:
            api_key: Optional API key for higher rate limits.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts for rate limits.
            max_retry_wait: Maximum seconds to wait for any single retry.
            retry_enabled: Whether to automatically retry on rate limits.
            status_callback: Function to call with status messages during retry.
                           If None, prints to stderr. Set to lambda x: None to silence.
        """
        self.api_key = api_key or os.environ.get("S2_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_wait = max_retry_wait
        self.retry_enabled = retry_enabled
        self.status_callback = status_callback or _default_status_callback
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

    def _calculate_backoff(self, attempt: int, retry_after: int | None) -> float:
        """Calculate wait time with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (0-indexed).
            retry_after: Server-suggested wait time, if any.

        Returns:
            Seconds to wait before next retry.
        """
        if retry_after:
            # Respect server's Retry-After, but cap it
            wait = min(retry_after, self.max_retry_wait)
        else:
            # Exponential backoff: 1s, 2s, 4s, 8s, ...
            wait = min(DEFAULT_BASE_DELAY * (2 ** attempt), self.max_retry_wait)

        # Add jitter (±25%) to prevent thundering herd
        jitter = wait * 0.25 * (random.random() * 2 - 1)
        return max(0.5, wait + jitter)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make HTTP request with automatic retry on rate limits.

        Shows countdown while waiting for retry.
        """
        last_error: RateLimitError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                if method == "GET":
                    response = self.client.get(url, **kwargs)
                elif method == "POST":
                    response = self.client.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Success or non-retryable error
                if response.status_code != 429:
                    return response

                # Rate limited - prepare for retry
                retry_after = _parse_retry_after(response)
                last_error = RateLimitError(retry_after=retry_after)

                if not self.retry_enabled or attempt >= self.max_retries:
                    raise last_error

                # Calculate wait time
                wait_seconds = self._calculate_backoff(attempt, retry_after)

                # Show countdown
                self._wait_with_countdown(wait_seconds, attempt + 1, self.max_retries)

            except httpx.RequestError as e:
                # Network errors - don't retry
                raise APIError(
                    code="NETWORK_ERROR",
                    message=str(e),
                    suggestion="Check your internet connection",
                )

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise APIError(code="UNKNOWN", message="Request failed")

    def _wait_with_countdown(self, wait_seconds: float, attempt: int, max_attempts: int) -> None:
        """Wait with a countdown display."""
        end_time = time.time() + wait_seconds
        retry_time = time.strftime("%H:%M:%S", time.localtime(end_time))

        while True:
            remaining = end_time - time.time()
            if remaining <= 0:
                break

            # Show status with countdown
            if remaining >= 1:
                msg = f"Rate limited. Retry {attempt}/{max_attempts} in {int(remaining)}s (at {retry_time})..."
            else:
                msg = f"Rate limited. Retrying now..."

            self.status_callback(msg)
            time.sleep(min(0.5, remaining))

        # Clear the status line
        _default_status_clear()

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
            retry_after = _parse_retry_after(response)
            raise RateLimitError(retry_after=retry_after)
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
            "limit": min(limit, 100),
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

        response = self._request_with_retry("GET", f"{GRAPH_API_BASE}/paper/search", params=params)
        return self._handle_response(response)

    def get_paper(self, paper_id: str, fields: str | None = None) -> dict[str, Any]:
        """Get details for a single paper."""
        params = {"fields": fields or DEFAULT_PAPER_FIELDS}
        encoded_id = quote(paper_id, safe=":")
        response = self._request_with_retry("GET", f"{GRAPH_API_BASE}/paper/{encoded_id}", params=params)
        return self._handle_response(response)

    def get_papers_batch(
        self, paper_ids: list[str], fields: str | None = None
    ) -> list[dict[str, Any]]:
        """Get details for multiple papers (batch endpoint)."""
        params = {"fields": fields or DEFAULT_PAPER_FIELDS}
        response = self._request_with_retry(
            "POST",
            f"{GRAPH_API_BASE}/paper/batch",
            params=params,
            json={"ids": paper_ids[:500]},
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
        response = self._request_with_retry(
            "GET", f"{GRAPH_API_BASE}/paper/{encoded_id}/citations", params=params
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
        response = self._request_with_retry(
            "GET", f"{GRAPH_API_BASE}/paper/{encoded_id}/references", params=params
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
        response = self._request_with_retry("GET", f"{GRAPH_API_BASE}/author/search", params=params)
        return self._handle_response(response)

    def get_author(self, author_id: str, fields: str | None = None) -> dict[str, Any]:
        """Get details for a single author."""
        params = {"fields": fields or DEFAULT_AUTHOR_FIELDS}
        response = self._request_with_retry("GET", f"{GRAPH_API_BASE}/author/{author_id}", params=params)
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
        response = self._request_with_retry(
            "GET", f"{GRAPH_API_BASE}/author/{author_id}/papers", params=params
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
        response = self._request_with_retry(
            "GET", f"{RECOMMENDATIONS_API_BASE}/papers/forpaper/{encoded_id}", params=params
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

        response = self._request_with_retry(
            "POST",
            f"{RECOMMENDATIONS_API_BASE}/papers/",
            params=params,
            json=payload,
        )
        return self._handle_response(response)

    # Dataset endpoints

    def list_releases(self) -> list[str]:
        """List available dataset releases."""
        response = self._request_with_retry("GET", f"{DATASETS_API_BASE}/release/")
        return self._handle_response(response)

    def get_release(self, release_id: str) -> dict[str, Any]:
        """Get datasets in a release."""
        response = self._request_with_retry("GET", f"{DATASETS_API_BASE}/release/{release_id}")
        return self._handle_response(response)

    def get_dataset_links(self, release_id: str, dataset_name: str) -> dict[str, Any]:
        """Get download links for a dataset."""
        response = self._request_with_retry(
            "GET", f"{DATASETS_API_BASE}/release/{release_id}/dataset/{dataset_name}"
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
