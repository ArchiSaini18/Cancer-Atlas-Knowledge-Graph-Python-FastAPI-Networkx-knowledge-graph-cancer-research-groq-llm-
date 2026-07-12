'''🧬 3CA Knowledge Graph — Cancer Dataset Explorer '''

This project builds a unified **knowledge graph** for the [Weizmann Institute 3CA (Curated Cancer Cell Atlas)](https://www.weizmann.ac.il/sites/3CA/), connecting **124+ single-cell RNA-seq (scRNA-seq) cancer datasets** through shared diseases, technologies, authors, and cancer types — exposed via a REST API, an interactive D3.js graph explorer, and an AI natural language chat interface.

🚀 Live Application

👉 API Docs: `http://localhost:8000/docs` (after running locally — see Quick Start below)
👉 Graph Explorer UI: `http://localhost:8000`

📌 Project Overview

The 3CA collection hosts 124 studies across 15 cancer types and 5.6M+ cells — but each dataset lives in isolation. You can't easily answer questions like:

* Which lung cancer studies share diseases with brain cancer studies?
* What technologies are most used for pancreatic cancer?
* Which authors published across multiple cancer types?
* Are there cross-cancer disease patterns hiding in the data?

This system solves that by:

* Scraping structured metadata for all 124+ studies from the 3CA website
* Building a **knowledge graph** (NetworkX MultiDiGraph) linking studies, cancer types, diseases, technologies, and authors
* Exposing the graph through a **FastAPI** REST backend
* Visualizing it with an interactive **D3.js force-directed graph**
* Answering natural-language questions about the graph using **Groq Llama-3.3-70B**

📂 Dataset

* **Source:** Scraped directly from the [Weizmann 3CA website](https://www.weizmann.ac.il/sites/3CA/)
* **Studies:** ~124 scRNA-seq cancer studies
* **Cancer Types:** 15
* **Cells:** 5.6M+
* **Graph Size:** ~287 nodes, ~1,842 edges (Study, CancerType, Disease, Technology, Author)

🛠️ Technologies Used

* **Python 3.10+**
* **NetworkX** – Knowledge graph construction (MultiDiGraph)
* **FastAPI** – REST API backend
* **BeautifulSoup + Requests** – Web scraping
* **D3.js** – Interactive force-directed graph frontend
* **Groq (Llama-3.3-70B)** – Natural language Q&A over the graph

🕸️ Graph Design

**Node Types:** `Study` · `CancerType` · `Disease` · `Technology` · `Author`

**Edge Types:** `BELONGS_TO` · `STUDIES_DISEASE` · `USES_TECHNOLOGY` · `AUTHORED_BY` · `SHARES_DISEASE` · `SHARES_TECHNOLOGY`

Cross-cancer `SHARES_DISEASE` edges are weighted **2.0** (vs 1.0 for same-cancer edges) to surface the biologically interesting cases where *different* cancer types study the *same* disease subtype.

🖥️ Application Features

✔ Interactive force-directed graph with filters by cancer type & technology
✔ Click any node → detail panel with study metadata and download links
✔ Full-text search with autocomplete across studies
✔ AI chat interface to query the graph in plain English
✔ BFS neighborhood expansion for exploring connected studies
✔ GraphML export for Gephi / Cytoscape

📈 Visualization

* Force-directed graph layout (D3.js)
* Node coloring by type (Study / CancerType / Disease / Technology / Author)
* Degree centrality-based node sizing to highlight hub studies
* GraphML export for publication-quality layouts in Gephi/Cytoscape

🔮 Future Improvements

* Replace NetworkX with **Neo4j** for Cypher queries at scale
* Extend to a **gene-level graph** with meta-programs and marker genes
* Add **semantic similarity edges** using paper-abstract embeddings (PubMed)
* Parse actual `.h5ad` expression matrices for cell-type composition
* Add a **citation graph overlay** via the CrossRef API
* Temporal (year-over-year) edges to track research trends

📖 About

The 3CA Knowledge Graph connects 124+ single-cell cancer studies from the Weizmann Institute's Curated Cancer Cell Atlas into a single explorable graph — surfacing cross-cancer relationships between diseases, sequencing technologies, and authors that are invisible when datasets are viewed in isolation. It combines a Python/NetworkX graph pipeline, a FastAPI backend, a D3.js visual explorer, and an LLM-powered natural language interface.

⚙️ Quick Start

```bash
git clone <your-repo>
cd 3ca-knowledge-graph

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # add your Groq API key

python -m scripts.run_pipeline  # scrape + build the graph

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` for the graph explorer or `http://localhost:8000/docs` for the API docs.

📦 Project Structure

```
3ca-knowledge-graph/
├── README.md
├── requirements.txt
├── scripts/
│   ├── scrape_3ca.py
│   └── run_pipeline.py
├── backend/
│   ├── main.py
│   └── graph_builder.py
├── frontend/
│   └── index.html
└── data/
    ├── 3ca_datasets.json
    ├── graph.json
    └── graph.graphml
```

Languages

* Python
* HTML / JavaScript (D3.js)


