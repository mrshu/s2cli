"""Tests for CLI commands."""

import json

from typer.testing import CliRunner

from s2cli.cli import app

runner = CliRunner()


class TestSearchCommand:
    def test_search_json_output(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "data": [{"paperId": "123", "title": "Test Paper", "year": 2023}],
                "total": 1,
            }
        )

        result = runner.invoke(app, ["search", "test query", "--json"])

        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert "results" in output or "data" in output

    def test_search_bibtex_output(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "data": [
                    {
                        "paperId": "123",
                        "title": "Test Paper",
                        "year": 2023,
                        "authors": [{"name": "John Doe"}],
                    }
                ],
                "total": 1,
            }
        )

        result = runner.invoke(app, ["search", "test", "--bibtex"])

        assert result.exit_code == 0
        assert "@article{" in result.stdout
        assert "Test Paper" in result.stdout

    def test_search_with_filters(self, httpx_mock):
        httpx_mock.add_response(json={"data": [], "total": 0})

        result = runner.invoke(
            app,
            ["search", "ML", "--year", "2020-2023", "--min-citations", "100"],
        )

        assert result.exit_code == 0
        request = httpx_mock.get_request()
        assert "year=2020-2023" in str(request.url)
        assert "minCitationCount=100" in str(request.url)


class TestPaperCommand:
    def test_get_paper(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "paperId": "abc123",
                "title": "Attention Is All You Need",
                "year": 2017,
                "authors": [{"name": "Ashish Vaswani"}],
            }
        )

        result = runner.invoke(app, ["paper", "abc123", "--json"])

        assert result.exit_code == 0
        assert "Attention Is All You Need" in result.stdout

    def test_get_paper_bibtex(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "paperId": "abc123",
                "title": "Test",
                "year": 2020,
                "authors": [],
            }
        )

        result = runner.invoke(app, ["paper", "abc123", "--bibtex"])

        assert result.exit_code == 0
        assert "@article{" in result.stdout

    def test_get_multiple_papers(self, httpx_mock):
        httpx_mock.add_response(
            json=[
                {"paperId": "1", "title": "Paper 1", "year": 2020, "authors": []},
                {"paperId": "2", "title": "Paper 2", "year": 2021, "authors": []},
            ]
        )

        result = runner.invoke(app, ["paper", "1", "2", "--json"])

        assert result.exit_code == 0


class TestCitationsCommand:
    def test_get_citations(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "data": [
                    {"citingPaper": {"paperId": "c1", "title": "Citing Paper"}}
                ]
            }
        )

        result = runner.invoke(app, ["citations", "abc123", "--json"])

        assert result.exit_code == 0


class TestReferencesCommand:
    def test_get_references(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "data": [
                    {"citedPaper": {"paperId": "r1", "title": "Referenced Paper"}}
                ]
            }
        )

        result = runner.invoke(app, ["references", "abc123", "--json"])

        assert result.exit_code == 0


class TestRecommendCommand:
    def test_get_recommendations(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "recommendedPapers": [
                    {"paperId": "r1", "title": "Recommended", "year": 2022, "authors": []}
                ]
            }
        )

        result = runner.invoke(app, ["recommend", "abc123", "--json"])

        assert result.exit_code == 0


class TestBibtexCommand:
    def test_bibtex_single(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "paperId": "123",
                "title": "Test Paper",
                "year": 2023,
                "authors": [{"name": "Jane Doe"}],
                "venue": "NeurIPS",
            }
        )

        result = runner.invoke(app, ["bibtex", "123"])

        assert result.exit_code == 0
        assert "@" in result.stdout
        assert "Test Paper" in result.stdout

    def test_bibtex_multiple(self, httpx_mock):
        httpx_mock.add_response(
            json=[
                {"paperId": "1", "title": "First", "year": 2020, "authors": []},
                {"paperId": "2", "title": "Second", "year": 2021, "authors": []},
            ]
        )

        result = runner.invoke(app, ["bibtex", "1", "2"])

        assert result.exit_code == 0
        assert "First" in result.stdout
        assert "Second" in result.stdout


class TestAuthorCommands:
    def test_author_get(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "authorId": "123",
                "name": "Geoffrey Hinton",
                "paperCount": 500,
            }
        )

        result = runner.invoke(app, ["author", "get", "123", "--json"])

        assert result.exit_code == 0
        assert "Geoffrey Hinton" in result.stdout

    def test_author_search(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "data": [{"authorId": "123", "name": "Yann LeCun"}],
                "total": 1,
            }
        )

        result = runner.invoke(app, ["author", "search", "LeCun", "--json"])

        assert result.exit_code == 0

    def test_author_papers(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "data": [
                    {"paperId": "p1", "title": "Paper 1", "year": 2020, "authors": []}
                ]
            }
        )

        result = runner.invoke(app, ["author", "papers", "123", "--json"])

        assert result.exit_code == 0


class TestDatasetCommands:
    def test_list_datasets(self, httpx_mock):
        httpx_mock.add_response(json=["2024-01-01", "2024-01-08", "2024-01-15"])

        result = runner.invoke(app, ["datasets", "--json"])

        assert result.exit_code == 0

    def test_get_dataset(self, httpx_mock):
        httpx_mock.add_response(
            json={
                "release_id": "2024-01-01",
                "datasets": [{"name": "papers", "description": "Paper data"}],
            }
        )

        result = runner.invoke(app, ["dataset", "2024-01-01", "--json"])

        assert result.exit_code == 0


class TestErrorHandling:
    def test_not_found_error(self, httpx_mock):
        httpx_mock.add_response(status_code=404)

        result = runner.invoke(app, ["paper", "nonexistent", "--json"])

        assert result.exit_code == 1
        assert "error" in result.stdout.lower() or "not found" in result.stdout.lower()

    def test_rate_limit_error_no_retry(self, httpx_mock):
        httpx_mock.add_response(status_code=429)

        result = runner.invoke(app, ["search", "test", "--json", "--no-retry"])

        assert result.exit_code == 1


class TestNoArgsShowsHelp:
    def test_no_args(self):
        result = runner.invoke(app, [])

        # Typer returns exit code 0 when showing help via no_args_is_help
        assert result.exit_code == 0 or "Usage" in result.stdout
        assert "search" in result.stdout.lower() or "Usage" in result.stdout
