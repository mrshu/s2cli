# s2cli - Semantic Scholar CLI

A command-line interface for the [Semantic Scholar API](https://api.semanticscholar.org/), designed for both human researchers and AI agents.

## Installation

```bash
pip install s2cli
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install s2cli
```

## Quick Start

Run directly without installing using [uvx](https://docs.astral.sh/uv/guides/tools/):

```bash
uvx s2cli search "attention mechanism transformers"
```

Or after installing:

```bash
# Search for papers (shows table in terminal)
s2cli search "attention mechanism transformers"

# Get paper details
s2cli paper ARXIV:1706.03762

# Export BibTeX
s2cli bibtex ARXIV:1706.03762 >> references.bib

# Get papers citing this paper
s2cli citations 204e3073870fae3d05bcbc2f6a8e263d9b72e776

# Get paper recommendations
s2cli recommend 204e3073870fae3d05bcbc2f6a8e263d9b72e776
```

## Output Formats

s2cli is designed to work seamlessly for both humans and AI agents:

| Context | Default Output | Behavior |
|---------|----------------|----------|
| Terminal (interactive) | Human-readable table | Easy to scan and read |
| Piped to another command | Compact JSON | Machine-parseable for scripts |
| `--json` flag | Pretty JSON | Explicit JSON when you need it |
| `--bibtex` / `-b` flag | BibTeX | Ready for LaTeX |

```bash
# Terminal: shows a nice table
s2cli search "transformers"

# Piped: automatically outputs JSON for jq, scripts, AI agents
s2cli search "transformers" | jq '.results[0].title'

# Explicit JSON (pretty-printed in terminal)
s2cli search "transformers" --json

# BibTeX output
s2cli search "transformers" --bibtex
```

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
| `s2cli author get <id>` | Get author details |
| `s2cli author search <name>` | Search authors by name |
| `s2cli author papers <id>` | Get author's papers |

### Dataset Commands

| Command | Description |
|---------|-------------|
| `s2cli datasets` | List available dataset releases |
| `s2cli dataset <release>` | Get dataset info |

## Search Filters

```bash
# Filter by year
s2cli search "LLM" --year 2023
s2cli search "LLM" --year 2020-2024

# Filter by minimum citations
s2cli search "attention" --min-citations 1000

# Only open access papers
s2cli search "BERT" --open-access

# Filter by venue
s2cli search "vision" --venue "CVPR,ICCV"

# Combine filters
s2cli search "transformers" --year 2022- --min-citations 500 --open-access
```

## Examples

### Human Workflows

```bash
# Find influential papers on a topic
s2cli search "large language models" --min-citations 1000

# Get all papers by an author
s2cli author papers 1741101 --limit 50

# Export bibliography for a set of papers
s2cli bibtex paper1 paper2 paper3 > refs.bib

# Explore citation network
s2cli citations 204e3073870fae3d05bcbc2f6a8e263d9b72e776 --limit 20
```

### AI Agent / Scripting Workflows

```bash
# Quick context gathering (auto-JSON when piped)
s2cli search "retrieval augmented generation" | jq '.results[:3]'

# Batch lookup with specific fields
s2cli paper id1 id2 id3 --fields paperId,title,year,citationCount

# Get top cited paper
s2cli search "NLP" --min-citations 5000 --limit 1 | jq '.results[0]'

# Extract just titles
s2cli search "vision transformers" | jq -r '.results[].title'
```

## Paper ID Formats

The CLI accepts various paper ID formats:

- Semantic Scholar ID: `204e3073870fae3d05bcbc2f6a8e263d9b72e776`
- DOI: `DOI:10.18653/v1/N18-3011` or `10.18653/v1/N18-3011`
- arXiv: `ARXIV:1706.03762` or `arXiv:1706.03762`
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

## Design Philosophy

Based on [CLI best practices](https://clig.dev/) and [GitHub CLI](https://cli.github.com/) patterns:

1. **Human-first by default** - Tables and readable output in terminals
2. **Machine-friendly when piped** - Automatic JSON for scripts and AI agents
3. **Explicit overrides** - `--json` and `--bibtex` flags when you need control
4. **BibTeX included** - Every paper result can include a citation

## License

MIT
