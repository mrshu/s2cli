"""Tests for BibTeX formatting."""

from s2cli.formatters.bibtex import (
    _escape_bibtex,
    _generate_cite_key,
    _get_entry_type,
    _normalize_text,
    format_bibtex_output,
    to_bibtex,
)


class TestNormalizeText:
    def test_ascii_unchanged(self):
        assert _normalize_text("hello world") == "hello world"

    def test_unicode_normalized(self):
        assert _normalize_text("café") == "cafe"
        assert _normalize_text("naïve") == "naive"

    def test_accented_names(self):
        assert _normalize_text("José García") == "Jose Garcia"


class TestEscapeBibtex:
    def test_ampersand(self):
        assert _escape_bibtex("Smith & Jones") == r"Smith \& Jones"

    def test_percent(self):
        assert _escape_bibtex("100% accurate") == r"100\% accurate"

    def test_special_chars(self):
        assert _escape_bibtex("$10") == r"\$10"
        assert _escape_bibtex("#1") == r"\#1"
        assert _escape_bibtex("under_score") == r"under\_score"

    def test_braces(self):
        assert _escape_bibtex("{test}") == r"\{test\}"

    def test_empty_string(self):
        assert _escape_bibtex("") == ""

    def test_none_returns_empty(self):
        assert _escape_bibtex(None) == ""


class TestGenerateCiteKey:
    def test_standard_paper(self):
        paper = {
            "authors": [{"name": "Ashish Vaswani"}],
            "year": 2017,
            "title": "Attention Is All You Need",
        }
        assert _generate_cite_key(paper) == "vaswani2017attention"

    def test_skips_stopwords(self):
        paper = {
            "authors": [{"name": "John Doe"}],
            "year": 2020,
            "title": "The Art of Programming",
        }
        assert _generate_cite_key(paper) == "doe2020art"

    def test_no_authors(self):
        paper = {"year": 2020, "title": "Anonymous Paper"}
        assert _generate_cite_key(paper) == "unknown2020anonymous"

    def test_no_year(self):
        paper = {"authors": [{"name": "Jane Smith"}], "title": "Timeless Work"}
        assert _generate_cite_key(paper) == "smithnodatetimeless"

    def test_no_title(self):
        paper = {"authors": [{"name": "Jane Smith"}], "year": 2020}
        assert _generate_cite_key(paper) == "smith2020paper"

    def test_unicode_author(self):
        paper = {
            "authors": [{"name": "José García"}],
            "year": 2020,
            "title": "Test Paper",
        }
        key = _generate_cite_key(paper)
        assert key == "garcia2020test"

    def test_multi_word_last_name(self):
        paper = {
            "authors": [{"name": "Vincent van Gogh"}],
            "year": 1888,
            "title": "Sunflowers",
        }
        assert _generate_cite_key(paper) == "gogh1888sunflowers"


class TestGetEntryType:
    def test_conference_venue_type(self):
        paper = {"publicationVenue": {"type": "conference"}}
        assert _get_entry_type(paper) == "inproceedings"

    def test_journal_venue_type(self):
        paper = {"publicationVenue": {"type": "journal"}}
        assert _get_entry_type(paper) == "article"

    def test_conference_in_venue_name(self):
        paper = {"venue": "Conference on Neural Information Processing Systems"}
        assert _get_entry_type(paper) == "inproceedings"

    def test_workshop_in_venue_name(self):
        paper = {"venue": "ACL Workshop on NLP"}
        assert _get_entry_type(paper) == "inproceedings"

    def test_journal_in_venue_name(self):
        paper = {"venue": "Journal of Machine Learning Research"}
        assert _get_entry_type(paper) == "article"

    def test_arxiv_defaults_to_article(self):
        paper = {"externalIds": {"ArXiv": "2106.12345"}}
        assert _get_entry_type(paper) == "article"

    def test_unknown_defaults_to_article(self):
        paper = {}
        assert _get_entry_type(paper) == "article"


class TestToBibtex:
    def test_basic_article(self):
        paper = {
            "paperId": "abc123",
            "title": "Test Paper",
            "authors": [{"name": "John Doe"}],
            "year": 2023,
            "venue": "Nature",
        }
        bib = to_bibtex(paper)
        assert "@article{doe2023test" in bib
        assert "title = {Test Paper}" in bib
        assert "author = {John Doe}" in bib
        assert "year = {2023}" in bib
        assert "journal = {Nature}" in bib

    def test_conference_paper(self):
        paper = {
            "paperId": "def456",
            "title": "Deep Learning Advances",
            "authors": [{"name": "Jane Smith"}, {"name": "Bob Wilson"}],
            "year": 2022,
            "venue": "Conference on Machine Learning",
        }
        bib = to_bibtex(paper)
        assert "@inproceedings{" in bib
        assert "booktitle = {Conference on Machine Learning}" in bib
        assert "author = {Jane Smith and Bob Wilson}" in bib

    def test_with_doi(self):
        paper = {
            "paperId": "xyz",
            "title": "Paper with DOI",
            "authors": [],
            "year": 2021,
            "externalIds": {"DOI": "10.1234/example"},
        }
        bib = to_bibtex(paper)
        assert "doi = {10.1234/example}" in bib

    def test_with_arxiv(self):
        paper = {
            "paperId": "xyz",
            "title": "ArXiv Paper",
            "authors": [],
            "year": 2021,
            "externalIds": {"ArXiv": "2106.12345"},
        }
        bib = to_bibtex(paper)
        assert "eprint = {2106.12345}" in bib
        assert "archiveprefix = {arXiv}" in bib

    def test_with_open_access_url(self):
        paper = {
            "paperId": "xyz",
            "title": "Open Paper",
            "authors": [],
            "year": 2021,
            "openAccessPdf": {"url": "https://example.com/paper.pdf"},
        }
        bib = to_bibtex(paper)
        assert "url = {https://example.com/paper.pdf}" in bib

    def test_escapes_special_chars_in_title(self):
        paper = {
            "paperId": "xyz",
            "title": "100% Accuracy & More",
            "authors": [],
            "year": 2021,
        }
        bib = to_bibtex(paper)
        assert r"100\% Accuracy \& More" in bib


class TestFormatBibtexOutput:
    def test_multiple_papers(self):
        papers = [
            {"paperId": "1", "title": "First", "authors": [], "year": 2020},
            {"paperId": "2", "title": "Second", "authors": [], "year": 2021},
        ]
        output = format_bibtex_output(papers)
        assert "@article{unknown2020first" in output
        assert "@article{unknown2021second" in output
        assert output.count("@article") == 2

    def test_skips_none_papers(self):
        papers = [
            {"paperId": "1", "title": "Valid", "authors": [], "year": 2020},
            None,
            {"paperId": "2", "title": "Also Valid", "authors": [], "year": 2021},
        ]
        output = format_bibtex_output(papers)
        assert output.count("@article") == 2

    def test_empty_list(self):
        assert format_bibtex_output([]) == ""
