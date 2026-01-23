"""Tests for Semantic Scholar API client."""

import pytest

from s2cli.api.client import (
    APIError,
    RateLimitError,
    SemanticScholarAPI,
    _parse_retry_after,
)


class TestParseRetryAfter:
    def test_parses_integer(self, httpx_mock):
        from httpx import Response

        response = Response(429, headers={"Retry-After": "30"})
        assert _parse_retry_after(response) == 30

    def test_returns_none_for_missing(self, httpx_mock):
        from httpx import Response

        response = Response(429)
        assert _parse_retry_after(response) is None

    def test_returns_none_for_invalid(self, httpx_mock):
        from httpx import Response

        response = Response(429, headers={"Retry-After": "invalid"})
        assert _parse_retry_after(response) is None


class TestAPIErrorToDict:
    def test_basic_error(self):
        error = APIError(code="TEST", message="Test error")
        d = error.to_dict()
        assert d["error"]["code"] == "TEST"
        assert d["error"]["message"] == "Test error"
        assert "documentation" in d["error"]

    def test_with_suggestion(self):
        error = APIError(code="TEST", message="Error", suggestion="Try this")
        d = error.to_dict()
        assert d["error"]["suggestion"] == "Try this"

    def test_with_status_code(self):
        error = APIError(code="TEST", message="Error", status_code=404)
        d = error.to_dict()
        assert d["error"]["status_code"] == 404


class TestSearchPapers:
    def test_basic_search(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": [{"paperId": "123", "title": "Test"}], "total": 1}
        )

        api = SemanticScholarAPI()
        result = api.search_papers("transformers")
        api.close()

        assert result["total"] == 1
        assert len(result["data"]) == 1
        assert result["data"][0]["paperId"] == "123"

    def test_search_with_filters(self, httpx_mock):
        httpx_mock.add_response(json={"data": [], "total": 0})

        api = SemanticScholarAPI()
        result = api.search_papers(
            "test",
            year="2020-2023",
            min_citation_count=100,
            open_access_pdf=True,
        )
        api.close()

        request = httpx_mock.get_request()
        assert "year=2020-2023" in str(request.url)
        assert "minCitationCount=100" in str(request.url)
        assert "openAccessPdf" in str(request.url)

    def test_limit_capped_at_100(self, httpx_mock):
        httpx_mock.add_response(json={"data": [], "total": 0})

        api = SemanticScholarAPI()
        api.search_papers("test", limit=500)
        api.close()

        request = httpx_mock.get_request()
        assert "limit=100" in str(request.url)


class TestGetPaper:
    def test_get_single_paper(self, httpx_mock):
        httpx_mock.add_response(
            json={"paperId": "abc123", "title": "Test Paper"}
        )

        api = SemanticScholarAPI()
        result = api.get_paper("abc123")
        api.close()

        assert result["paperId"] == "abc123"

    def test_paper_id_url_encoding(self, httpx_mock):
        httpx_mock.add_response(json={"paperId": "test"})

        api = SemanticScholarAPI()
        api.get_paper("ARXIV:2106.12345")
        api.close()

        request = httpx_mock.get_request()
        assert "ARXIV:2106.12345" in str(request.url)


class TestGetPapersBatch:
    def test_batch_request(self, httpx_mock):
        httpx_mock.add_response(
            json=[{"paperId": "1"}, {"paperId": "2"}]
        )

        api = SemanticScholarAPI()
        result = api.get_papers_batch(["1", "2"])
        api.close()

        assert len(result) == 2

    def test_batch_uses_post(self, httpx_mock):
        httpx_mock.add_response(json=[])

        api = SemanticScholarAPI()
        api.get_papers_batch(["1", "2"])
        api.close()

        request = httpx_mock.get_request()
        assert request.method == "POST"


class TestErrorHandling:
    def test_404_raises_not_found(self, httpx_mock):
        httpx_mock.add_response(status_code=404)

        api = SemanticScholarAPI()
        with pytest.raises(APIError) as exc:
            api.get_paper("nonexistent")
        api.close()

        assert exc.value.code == "NOT_FOUND"
        assert exc.value.status_code == 404

    def test_400_raises_bad_request(self, httpx_mock):
        httpx_mock.add_response(
            status_code=400, json={"message": "Invalid field"}
        )

        api = SemanticScholarAPI()
        with pytest.raises(APIError) as exc:
            api.search_papers("test")
        api.close()

        assert exc.value.code == "BAD_REQUEST"
        assert "Invalid field" in exc.value.message

    def test_429_raises_rate_limit(self, httpx_mock):
        httpx_mock.add_response(
            status_code=429, headers={"Retry-After": "60"}
        )

        api = SemanticScholarAPI(retry_enabled=False)
        with pytest.raises(RateLimitError) as exc:
            api.search_papers("test")
        api.close()

        assert exc.value.retry_after == 60

    def test_unknown_error(self, httpx_mock):
        httpx_mock.add_response(status_code=500)

        api = SemanticScholarAPI()
        with pytest.raises(APIError) as exc:
            api.search_papers("test")
        api.close()

        assert exc.value.code == "API_ERROR"
        assert exc.value.status_code == 500


class TestRetryBehavior:
    def test_retries_on_rate_limit(self, httpx_mock):
        # First request returns 429, second succeeds
        httpx_mock.add_response(
            status_code=429, headers={"Retry-After": "0"}
        )
        httpx_mock.add_response(json={"paperId": "123"})

        api = SemanticScholarAPI(
            max_retries=1,
            status_callback=lambda x: None,  # Silence output
        )
        result = api.get_paper("123")
        api.close()

        assert result["paperId"] == "123"
        assert len(httpx_mock.get_requests()) == 2

    def test_gives_up_after_max_retries(self, httpx_mock):
        # Initial + 2 retries = 3 requests, all return 429
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})

        api = SemanticScholarAPI(
            max_retries=2,
            retry_enabled=True,
            status_callback=lambda x: None,
        )
        with pytest.raises(RateLimitError):
            api.get_paper("123")
        api.close()

        assert len(httpx_mock.get_requests()) == 3

    def test_no_retry_when_disabled(self, httpx_mock):
        httpx_mock.add_response(status_code=429)

        api = SemanticScholarAPI(retry_enabled=False)
        with pytest.raises(RateLimitError):
            api.search_papers("test")
        api.close()

        assert len(httpx_mock.get_requests()) == 1


class TestAuthorEndpoints:
    def test_search_authors(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": [{"authorId": "123", "name": "John Doe"}], "total": 1}
        )

        api = SemanticScholarAPI()
        result = api.search_authors("John Doe")
        api.close()

        assert result["total"] == 1
        assert result["data"][0]["name"] == "John Doe"

    def test_get_author(self, httpx_mock):
        httpx_mock.add_response(
            json={"authorId": "123", "name": "Jane Smith"}
        )

        api = SemanticScholarAPI()
        result = api.get_author("123")
        api.close()

        assert result["authorId"] == "123"

    def test_get_author_papers(self, httpx_mock):
        httpx_mock.add_response(
            json={"data": [{"paperId": "p1"}, {"paperId": "p2"}]}
        )

        api = SemanticScholarAPI()
        result = api.get_author_papers("123")
        api.close()

        assert len(result["data"]) == 2


class TestRecommendations:
    def test_get_recommendations(self, httpx_mock):
        httpx_mock.add_response(
            json={"recommendedPapers": [{"paperId": "r1"}, {"paperId": "r2"}]}
        )

        api = SemanticScholarAPI()
        result = api.get_recommendations("123")
        api.close()

        assert len(result["recommendedPapers"]) == 2


class TestContextManager:
    def test_context_manager(self, httpx_mock):
        httpx_mock.add_response(json={"paperId": "123"})

        with SemanticScholarAPI() as api:
            result = api.get_paper("123")
            assert result["paperId"] == "123"
