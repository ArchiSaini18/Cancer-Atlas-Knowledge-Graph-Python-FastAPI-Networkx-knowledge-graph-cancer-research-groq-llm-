"""
3CA Knowledge Graph API
FastAPI backend serving graph data + AI-powered search via Groq
"""

import json
import os
import re
from pathlib import Path
from typing import Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
GRAPH_PATH = DATA_DIR / "graph.json"
DATASETS_PATH = DATA_DIR / "3ca_datasets.json"


def load_environment(base_dir: Optional[Path] = None) -> None:
    """Load environment variables from a local .env file or env example file."""
    root = Path(base_dir or BASE_DIR)
    env_candidates = [
        root / ".env",
        root / "env.example.txt",
        root / ".env.example",
    ]

    for env_path in env_candidates:
        if not env_path.exists():
            continue

        with open(env_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

        print(f"Loaded environment from {env_path}")
        break


app = FastAPI(
    title="3CA Knowledge Graph API",
    description="Unified knowledge graph for Weizmann 3CA cancer scRNA-seq datasets",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load data at startup ──────────────────────────────────────────────────────
_graph_data: dict = {}
_datasets_data: dict = {}
_groq_client: Optional[Groq] = None


@app.on_event("startup")
async def startup_event():
    global _graph_data, _datasets_data, _groq_client

    load_environment()

    if GRAPH_PATH.exists():
        with open(GRAPH_PATH) as f:
            _graph_data = json.load(f)
        print(f"Loaded graph: {_graph_data['stats']['total_nodes']} nodes, "
              f"{_graph_data['stats']['total_edges']} edges")
    else:
        print("WARNING: graph.json not found. Run the pipeline first.")
        _graph_data = {"nodes": [], "edges": [], "stats": {}}

    if DATASETS_PATH.exists():
        with open(DATASETS_PATH) as f:
            _datasets_data = json.load(f)
        print(f"Loaded {_datasets_data.get('total_studies', 0)} studies")

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        _groq_client = Groq(api_key=groq_key)
        print("Groq client initialized")
    else:
        print("WARNING: GROQ_API_KEY not set. AI search will be disabled.")


# ── Pydantic Models ───────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    max_results: int = 10


class AIQueryRequest(BaseModel):
    question: str


# ── Helper functions ──────────────────────────────────────────────────────────
def get_study_nodes() -> list[dict]:
    return [n for n in _graph_data.get("nodes", []) if n.get("type") == "Study"]


def get_edges_for_node(node_id: str) -> list[dict]:
    return [e for e in _graph_data.get("edges", [])
            if e["source"] == node_id or e["target"] == node_id]


def build_context_for_ai() -> str:
    """Build a condensed context string for the AI from graph data."""
    studies = get_study_nodes()
    cancer_counts = defaultdict(int)
    disease_counts = defaultdict(int)
    tech_counts = defaultdict(int)
    
    for s in studies:
        cancer_counts[s.get("cancer_type", "Unknown")] += 1
        disease_counts[s.get("disease_subtype", "Unknown")] += 1
        tech_counts[s.get("technology", "Unknown")] += 1

    lines = [
        "=== 3CA Knowledge Graph Context ===",
        f"Total studies: {len(studies)}",
        "",
        "Studies by cancer type:",
    ]
    for ct, count in sorted(cancer_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {ct}: {count} studies")

    lines += ["", "Common diseases:"]
    for d, count in sorted(disease_counts.items(), key=lambda x: -x[1])[:15]:
        if d:
            lines.append(f"  {d}: {count} studies")

    lines += ["", "Technologies used:"]
    for t, count in sorted(tech_counts.items(), key=lambda x: -x[1]):
        if t:
            lines.append(f"  {t}: {count} studies")

    lines += ["", "Sample studies:"]
    for s in studies[:20]:
        lines.append(
            f"  [{s.get('cancer_type')}] {s.get('label')} | "
            f"Disease: {s.get('disease_subtype')} | "
            f"Tech: {s.get('technology')} | "
            f"Cells: {s.get('num_cells', 0):,}"
        )

    return "\n".join(lines)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "graph_loaded": bool(_graph_data.get("nodes")),
        "ai_enabled": _groq_client is not None,
        "stats": _graph_data.get("stats", {}),
    }


@app.get("/api/graph")
async def get_graph(
    node_types: Optional[str] = Query(None, description="Comma-separated node types to include"),
    limit_nodes: int = Query(500, description="Max nodes to return"),
):
    """Return the full graph or a filtered subset."""
    nodes = _graph_data.get("nodes", [])
    edges = _graph_data.get("edges", [])

    if node_types:
        allowed = set(node_types.split(","))
        nodes = [n for n in nodes if n.get("type") in allowed]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in edges
                 if e["source"] in node_ids and e["target"] in node_ids]

    # Limit for performance
    nodes = nodes[:limit_nodes]
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges
             if e["source"] in node_ids and e["target"] in node_ids]

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": _graph_data.get("stats", {}),
    }


@app.get("/api/stats")
async def get_stats():
    """Return high-level statistics."""
    studies = get_study_nodes()
    cancer_counts = defaultdict(lambda: {"studies": 0, "cells": 0, "samples": 0})

    for s in studies:
        ct = s.get("cancer_type", "Unknown")
        cancer_counts[ct]["studies"] += 1
        cancer_counts[ct]["cells"] += s.get("num_cells", 0)
        cancer_counts[ct]["samples"] += s.get("num_samples", 0)

    tech_counts = defaultdict(int)
    for s in studies:
        tech_counts[s.get("technology", "Unknown")] += 1

    return {
        "total_studies": len(studies),
        "total_cells": sum(s.get("num_cells", 0) for s in studies),
        "total_samples": sum(s.get("num_samples", 0) for s in studies),
        "cancer_types": dict(cancer_counts),
        "technologies": dict(tech_counts),
        "graph_stats": _graph_data.get("stats", {}),
    }


@app.get("/api/studies")
async def list_studies(
    cancer_type: Optional[str] = None,
    technology: Optional[str] = None,
    disease: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    min_cells: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List and filter studies."""
    studies = get_study_nodes()

    if cancer_type:
        studies = [s for s in studies
                   if s.get("cancer_type", "").lower() == cancer_type.lower()]
    if technology:
        studies = [s for s in studies
                   if s.get("technology", "").lower() == technology.lower()]
    if disease:
        studies = [s for s in studies
                   if disease.lower() in s.get("disease_subtype", "").lower()]
    if year_from:
        studies = [s for s in studies if (s.get("year") or 0) >= year_from]
    if year_to:
        studies = [s for s in studies if (s.get("year") or 9999) <= year_to]
    if min_cells:
        studies = [s for s in studies if s.get("num_cells", 0) >= min_cells]

    total = len(studies)
    studies = studies[offset: offset + limit]

    return {"total": total, "studies": studies, "offset": offset, "limit": limit}


@app.get("/api/studies/{study_id}")
async def get_study(study_id: str):
    """Get a single study with its neighborhood in the graph."""
    full_id = f"study_{study_id}" if not study_id.startswith("study_") else study_id
    
    node = next((n for n in _graph_data.get("nodes", []) if n["id"] == full_id), None)
    if not node:
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")

    # Get neighbors
    edges = get_edges_for_node(full_id)
    neighbor_ids = set()
    for e in edges:
        neighbor_ids.add(e["source"])
        neighbor_ids.add(e["target"])
    neighbor_ids.discard(full_id)

    neighbors = [n for n in _graph_data.get("nodes", []) if n["id"] in neighbor_ids]

    return {
        "study": node,
        "edges": edges,
        "neighbors": neighbors,
    }


@app.post("/api/search")
async def search_studies(req: SearchRequest):
    """Full-text search across study metadata."""
    query = req.query.lower()
    studies = get_study_nodes()

    scored = []
    for s in studies:
        score = 0
        searchable = " ".join([
            s.get("label", ""),
            s.get("cancer_type", ""),
            s.get("disease_subtype", ""),
            s.get("technology", ""),
            s.get("first_author", ""),
            str(s.get("year", "")),
        ]).lower()

        for token in query.split():
            if token in searchable:
                score += searchable.count(token)

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: -x[0])
    results = [s for _, s in scored[:req.max_results]]

    return {"query": req.query, "results": results, "total": len(results)}


@app.get("/api/relationships")
async def get_relationships(
    relation_type: Optional[str] = None,
    cross_cancer_only: bool = False,
):
    """Query specific relationship types in the graph."""
    edges = _graph_data.get("edges", [])

    if relation_type:
        edges = [e for e in edges if e.get("relation") == relation_type]
    if cross_cancer_only:
        edges = [e for e in edges if e.get("cross_cancer") is True]

    return {
        "relation_type": relation_type,
        "total": len(edges),
        "edges": edges[:500],  # cap for API safety
    }


@app.post("/api/ai/query")
async def ai_query(req: AIQueryRequest):
    """Natural language Q&A over the knowledge graph using Groq."""
    if not _groq_client:
        raise HTTPException(
            status_code=503,
            detail="AI search not available. Set GROQ_API_KEY environment variable."
        )

    context = build_context_for_ai()

    system_prompt = """You are a bioinformatics expert assistant analyzing the 3CA 
(Curated Cancer Cell Atlas) knowledge graph from the Weizmann Institute of Science.
The graph contains single-cell RNA sequencing (scRNA-seq) cancer datasets connected 
by shared diseases, technologies, cancer types, and authors.

Answer questions accurately based on the provided context. Be specific about:
- Study counts and statistics
- Relationships between datasets
- Research patterns and insights
- Data availability (downloads, meta-programs, CNAs, etc.)

Keep answers concise but informative. Use markdown formatting."""

    user_message = f"""Context from the 3CA Knowledge Graph:

{context}

User Question: {req.question}"""

    try:
        response = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq API error: {str(e)}")

    return {
        "question": req.question,
        "answer": answer,
        "model": "llama-3.3-70b-versatile",
    }


@app.get("/api/neighbors/{node_id}")
async def get_neighbors(node_id: str, depth: int = Query(1, le=2)):
    """Get node neighborhood up to specified depth."""
    all_nodes = {n["id"]: n for n in _graph_data.get("nodes", [])}
    all_edges = _graph_data.get("edges", [])
    
    if node_id not in all_nodes:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    visited = {node_id}
    frontier = {node_id}
    result_edges = []

    for _ in range(depth):
        next_frontier = set()
        for nid in frontier:
            for e in all_edges:
                if e["source"] == nid:
                    result_edges.append(e)
                    if e["target"] not in visited:
                        next_frontier.add(e["target"])
                        visited.add(e["target"])
        frontier = next_frontier

    result_nodes = [all_nodes[nid] for nid in visited if nid in all_nodes]
    return {"nodes": result_nodes, "edges": result_edges, "center": node_id}


# Serve frontend in production
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
