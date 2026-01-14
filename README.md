# s2cli - Semantic Scholar CLI

A command-line interface for the [Semantic Scholar API](https://api.semanticscholar.org/), designed for both human researchers and AI agents.

## Installation

```bash
pip install s2cli
```

## Quick Start

```bash
# Search for papers
s2cli search "attention mechanism transformers"

# Get paper details (supports DOI, arXiv ID, S2 ID)
s2cli paper DOI:10.48550/arXiv.1706.03762

# Export BibTeX
s2cli bibtex DOI:10.48550/arXiv.1706.03762 >> references.bib

# Get papers citing this paper
s2cli citations 649def34f8be52c8b66281af98ae884c09aef38b

# Get paper recommendations
s2cli recommend 649def34f8be52c8b66281af98ae884c09aef38b
```

## Features

- **JSON output by default** - Structured, parseable output for scripts and AI agents
- **BibTeX included** - Every paper result includes a BibTeX citation
- **Multiple output formats** - `--format json|table|bibtex`
- **Search filters** - `--year`, `--min-citations`, `--open-access`, `--venue`
- **Batch operations** - Look up multiple papers at once

## Commands

### Paper Commands

| Command | Description |
|---------|-------------|
| `s2cli search <query>` | Search papers by keyword |
| `s2cli paper <id>...` | Get paper details (batch supported) |
| `s2cli citations <id>` | Get papers citing this paper |
| `s2cli references <id>` | Get papers cited by this paper |
| `s2cli recommend <id>` | Get paper recommendations |
| `s2cli bibtex <id>...` | Export BibTeX only |

### Author Commands

| Command | Description |
|---------|-------------|
| `s2cli author <id>` | Get author details |
| `s2cli author search <name>` | Search authors by name |
| `s2cli author papers <id>` | Get author's papers |

### Dataset Commands

| Command | Description |
|---------|-------------|
| `s2cli datasets` | List available dataset releases |
| `s2cli dataset <release>` | Get dataset info |

## Examples

### Human Workflows

```bash
# Find influential papers on a topic
s2cli search "large language models" --min-citations 1000 -f table

# Get all papers by an author
s2cli author papers 1741101 --limit 50

# Export bibliography for a set of papers
s2cli bibtex paper1 paper2 paper3 > refs.bib
```

### AI Agent Workflows

```bash
# Quick context gathering (minimal fields)
s2cli search "retrieval augmented generation" --fields paperId,title,tldr,citationCount

# Batch lookup
s2cli paper id1 id2 id3 --fields title,authors,year

# Pipe to jq for filtering
s2cli search "NLP" | jq '.results[] | select(.citationCount > 100)'
```

## Paper ID Formats

The CLI accepts various paper ID formats:

- Semantic Scholar ID: `649def34f8be52c8b66281af98ae884c09aef38b`
- DOI: `DOI:10.18653/v1/N18-3011` or `10.18653/v1/N18-3011`
- arXiv: `ARXIV:2106.15928` or `arXiv:2106.15928`
- CorpusId: `CorpusId:215416146`
- PubMed: `PMID:123456`

## Configuration

Set your API key for higher rate limits:

```bash
export S2_API_KEY=your_key_here
```

Or pass it directly:

```bash
s2cli search "query" --api-key your_key_here
```

## License

MIT
