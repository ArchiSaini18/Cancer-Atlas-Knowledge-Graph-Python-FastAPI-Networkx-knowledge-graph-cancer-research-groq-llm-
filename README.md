# 3CA Knowledge Graph

> A unified knowledge graph for the [Weizmann Institute 3CA (Curated Cancer Cell Atlas)](https://www.weizmann.ac.il/sites/3CA/) — connecting 124+ scRNA-seq cancer datasets through shared diseases, technologies, authors, and cancer types.

![Graph Architecture](docs/graph-architecture.png)

---

## What This Solves

The 3CA collection hosts 124 studies across 15 cancer types, 5.6M+ cells. Each dataset lives in isolation — you can't easily answer:

- *Which lung cancer studies share diseases with brain cancer studies?*
- *What technologies are most used for pancreatic cancer?*
- *Which authors published across multiple cancer types?*
- *Are there cross-cancer disease patterns in the data?*

This system builds a **knowledge graph** that connects all datasets by their biological and methodological relationships, then exposes them through a REST API + interactive visual explorer + AI natural language interface.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   3CA Website (Weizmann)              │
│  15 cancer type pages × N studies each               │
└──────────────┬───────────────────────────────────────┘
               │  scrape_3ca.py (requests + BeautifulSoup)
               ▼
┌──────────────────────────────────────────────────────┐
│           data/3ca_datasets.json                      │
│  Structured metadata for all studies                  │
└──────────────┬───────────────────────────────────────┘
               │  graph_builder.py (NetworkX)
               ▼
┌──────────────────────────────────────────────────────┐
│  Knowledge Graph (MultiDiGraph)                       │
│                                                       │
│  Nodes:  Study │ CancerType │ Disease │ Tech │ Author │
│                                                       │
│  Edges:  BELONGS_TO · STUDIES_DISEASE                │
│          SHARES_DISEASE · USES_TECHNOLOGY             │
│          AUTHORED_BY · SHARES_TECHNOLOGY             │
└──────────────┬───────────────────────────────────────┘
               │  save as graph.json + graph.graphml
               ▼
┌──────────────────────────────────────────────────────┐
│            FastAPI Backend (main.py)                  │
│                                                       │
│  GET  /api/graph          → D3-ready graph JSON       │
│  GET  /api/stats          → Summary statistics        │
│  GET  /api/studies        → Filterable study list     │
│  GET  /api/studies/:id    → Study + neighborhood      │
│  POST /api/search         → Full-text search          │
│  POST /api/ai/query       → Groq LLM Q&A             │
│  GET  /api/neighbors/:id  → BFS neighborhood          │
│  GET  /api/relationships  → Edge type queries         │
└──────────────┬───────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────┐
│       Frontend (D3.js Force Graph)                    │
│                                                       │
│  • Interactive force-directed graph                   │
│  • Filter by cancer type & technology                 │
│  • Click any node → detail panel + download links     │
│  • Full-text search with autocomplete                 │
│  • AI chat (Groq Llama-3.3-70B) over the graph       │
└──────────────────────────────────────────────────────┘
```

---

## Graph Design

### Node Types

| Type | Description | Count (approx) |
|------|-------------|----------------|
| `Study` | Individual scRNA-seq study | ~124 |
| `CancerType` | Tissue/organ category (Lung, Breast…) | 15 |
| `Disease` | Disease subtype (Lung adenocarcinoma…) | ~40 |
| `Technology` | Sequencing platform (10x, SmartSeq2…) | ~6 |
| `Author` | First author of study | ~100+ |

### Edge Types

| Relation | Direction | Meaning |
|----------|-----------|---------|
| `BELONGS_TO` | Study → CancerType | Study is categorized under cancer type |
| `STUDIES_DISEASE` | Study → Disease | Study investigates specific disease |
| `USES_TECHNOLOGY` | Study → Technology | Study used this sequencing platform |
| `AUTHORED_BY` | Study → Author | First-author relationship |
| `SHARES_DISEASE` | Study ↔ Study | Two studies investigate same disease subtype — **cross-cancer weight=2.0** |
| `SHARES_TECHNOLOGY` | Study ↔ Study | Same sequencing platform |

### Key Design Decisions

**Why MultiDiGraph?** Allows multiple edges between the same pair of nodes (e.g. two studies can share both disease AND technology), and directed edges encode semantic meaning (Study → CancerType vs Author → Study).

**Cross-cancer SHARES_DISEASE edges have weight=2.0** (vs 1.0 for same-cancer) to highlight the biologically interesting finding that distinct cancer types study the same disease subtype.

**Centrality scoring**: NetworkX degree centrality is computed at build time and stored on each node, enabling ranking by "connectivity" in the graph — useful for finding hub studies or highly-connected disease subtypes.

**Technology node as hub**: By creating Technology nodes shared across studies, the graph surfaces platform-level community structure — e.g. all SmartSeq2 studies cluster together regardless of cancer type, enabling cross-study comparison of systematic effects.

---

## Quick Start

### 1. Clone & Setup

```bash
git clone <your-repo>
cd 3ca-knowledge-graph

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy env template
cp .env.example .env

# Edit .env and add your Groq API key
# Get a free key at: https://console.groq.com
nano .env
```

Your `.env` should contain:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Run the Pipeline (Scrape + Build Graph)

```bash
# Full pipeline: scrape 3CA website → build graph → save outputs
python -m scripts.run_pipeline

# If already scraped, skip scraping (uses cached data/3ca_datasets.json)
python -m scripts.run_pipeline --skip-scrape
```

Expected output:
```
=== 3CA Knowledge Graph Pipeline ===

[Step 1] Scraping 3CA website...
  [Lung] Scraping: https://www.weizmann.ac.il/sites/3CA/lung
  ...
  ✓ Scraped 124 studies in 12.3s

[Step 2] Building knowledge graph...
  ✓ Graph built in 0.45s
  ✓ Nodes: 287
  ✓ Edges: 1842

[Step 3] Saving outputs...
  Saved graph.json (287 nodes, 1842 edges)
  Saved graph.graphml
```

### 4. Start the API Server

```bash
# Load .env and start server
export $(cat .env | xargs)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the Explorer

- **Graph UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/api/health

---

## API Reference

### `GET /api/health`
Check server status and graph load state.

### `GET /api/graph?node_types=Study,CancerType&limit_nodes=400`
Full graph data in D3-compatible format. Optional filters: `node_types` (comma-separated), `limit_nodes`.

### `GET /api/stats`
Aggregate statistics: cancer type breakdowns, cell counts, technology distribution.

### `GET /api/studies?cancer_type=Lung&technology=10x&min_cells=10000`
Filterable study list. Params: `cancer_type`, `technology`, `disease`, `year_from`, `year_to`, `min_cells`, `limit`, `offset`.

### `GET /api/studies/{id}`
Single study with full neighborhood (connected nodes + edges).

### `POST /api/search`
```json
{ "query": "lung adenocarcinoma SmartSeq2", "max_results": 10 }
```
Ranked full-text search across title, cancer type, disease, technology, author.

### `POST /api/ai/query`
```json
{ "question": "Which studies have CNAs and meta-programs for breast cancer?" }
```
Natural language queries answered by Groq Llama-3.3-70B using the graph as context.

### `GET /api/relationships?relation_type=SHARES_DISEASE&cross_cancer_only=true`
Query specific edge types. Useful for finding cross-cancer disease connections.

### `GET /api/neighbors/{node_id}?depth=2`
BFS neighborhood expansion up to depth 2.

---

## Data Files

After running the pipeline:

```
data/
├── 3ca_datasets.json    # Raw scraped metadata (all studies)
├── graph.json           # Graph in D3-ready JSON format (nodes + edges)
└── graph.graphml        # GraphML for Gephi / Cytoscape import
```

### Import into Gephi (for publication-quality graphs)
1. File → Open → `data/graph.graphml`
2. Use "node_type" as partition color
3. Layout: ForceAtlas2 with LinLog mode

### Import into Cytoscape
1. File → Import → Network from File → `data/graph.graphml`
2. Style by `type` attribute

---

## Design Decisions & Trade-offs

### What I chose
- **NetworkX MultiDiGraph** over a dedicated graph DB (Neo4j/ArangoDB): zero infrastructure, easy to inspect, serializable to JSON. Trade-off: not suited for billion-edge scale.
- **Scraped metadata only** (not actual expression matrices): the .tar.gz files are GB-scale; connecting metadata is sufficient to demonstrate cross-dataset relationships.
- **Groq + Llama-3.3-70B** over OpenAI: free tier, fast inference (~200 tok/s), sufficient context window for the graph summary.
- **D3 force-directed graph** over Cytoscape.js or vis.js: more control, no npm dependency, works pure in-browser.

### Potential Extensions
- **Neo4j backend**: Replace NetworkX with a real graph DB for Cypher queries at scale
- **Gene-level graph**: Extend nodes to include meta-programs and marker genes (already linked from the site)
- **Semantic similarity edges**: Use embeddings of paper abstracts (fetched via PubMed) to add `SEMANTICALLY_SIMILAR` edges
- **Download + index actual data**: Parse the .h5ad files to add cell-type composition as node attributes, enabling "find studies with >30% T-cells"
- **Temporal analysis**: Year-over-year edges to track how cancer subtypes have been studied over time
- **Citation graph overlay**: CrossRef API to add `CITES` edges between studies

---

## Project Structure

```
3ca-knowledge-graph/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── scripts/
│   ├── scrape_3ca.py        # Web scraper for 3CA website
│   └── run_pipeline.py      # End-to-end pipeline runner
│
├── backend/
│   ├── main.py              # FastAPI app (all endpoints)
│   └── graph_builder.py     # Graph construction + export
│
├── frontend/
│   └── index.html           # Single-file D3 graph explorer
│
└── data/                    # Generated (not committed to git)
    ├── 3ca_datasets.json
    ├── graph.json
    └── graph.graphml
```

---

## Requirements

- Python 3.10+
- Internet access (for scraping; one-time)
- Groq API key (free at [console.groq.com](https://console.groq.com))

---

## License

MIT — See LICENSE for details.

Data sourced from the Weizmann Institute of Science 3CA project. Please cite the original studies when using this data.
