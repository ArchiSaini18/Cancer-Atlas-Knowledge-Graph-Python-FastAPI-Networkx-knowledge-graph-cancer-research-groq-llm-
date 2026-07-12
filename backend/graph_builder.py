"""
Knowledge Graph Builder for 3CA Cancer Datasets

Builds a multi-relational graph where nodes are:
  - Study (individual scRNA-seq study)
  - CancerType (e.g. Lung, Breast)
  - Disease (e.g. Lung adenocarcinoma, NSCLC)
  - Technology (e.g. 10x, SmartSeq2)
  - Author (first author)

Edges represent:
  - BELONGS_TO: Study -> CancerType
  - STUDIES_DISEASE: Study -> Disease
  - USES_TECHNOLOGY: Study -> Technology
  - AUTHORED_BY: Study -> Author
  - SHARES_DISEASE: Study <-> Study (same disease subtype)
  - SHARES_TECHNOLOGY: Study <-> Study (same technology)
  - CO_AUTHORED: Study <-> Study (same first author)
  - CROSS_CANCER: Study <-> Study (shared disease across cancer types)
"""

import json
import networkx as nx
from pathlib import Path
from collections import defaultdict
import re


def normalize(text: str) -> str:
    """Normalize text for node IDs."""
    return re.sub(r"[^a-z0-9_]", "_", text.lower().strip())


def build_graph(data: dict) -> nx.MultiDiGraph:
    """Build the knowledge graph from scraped dataset JSON."""
    G = nx.MultiDiGraph()
    studies = data["studies"]

    # ── Pass 1: Add all typed nodes ──────────────────────────────────────────
    for s in studies:
        sid = f"study_{s['id']}"
        G.add_node(sid,
                   type="Study",
                   label=s["title"],
                   first_author=s["first_author"],
                   year=s["year"],
                   cancer_type=s["cancer_type"],
                   disease_subtype=s["disease_subtype"],
                   technology=s["technology"],
                   num_samples=s["num_samples"],
                   num_cells=s["num_cells"],
                   paper_url=s["paper_url"],
                   data_url=s["data_url"],
                   has_meta_programs=s["has_meta_programs"],
                   has_cna=s["has_cna"],
                   has_umap=s["has_umap"],
                   has_cell_cycle=s["has_cell_cycle"])

        # Cancer type node
        ct_id = f"cancer_{normalize(s['cancer_type'])}"
        if not G.has_node(ct_id):
            G.add_node(ct_id, type="CancerType", label=s["cancer_type"])

        # Disease node
        if s["disease_subtype"]:
            d_id = f"disease_{normalize(s['disease_subtype'])}"
            if not G.has_node(d_id):
                G.add_node(d_id, type="Disease", label=s["disease_subtype"])

        # Technology node
        if s["technology"]:
            t_id = f"tech_{normalize(s['technology'])}"
            if not G.has_node(t_id):
                G.add_node(t_id, type="Technology", label=s["technology"])

        # Author node
        if s["first_author"]:
            a_id = f"author_{normalize(s['first_author'])}"
            if not G.has_node(a_id):
                G.add_node(a_id, type="Author", label=s["first_author"])

    # ── Pass 2: Add edges ────────────────────────────────────────────────────
    for s in studies:
        sid = f"study_{s['id']}"

        # Study -> CancerType
        ct_id = f"cancer_{normalize(s['cancer_type'])}"
        G.add_edge(sid, ct_id, relation="BELONGS_TO", weight=1.0)

        # Study -> Disease
        if s["disease_subtype"]:
            d_id = f"disease_{normalize(s['disease_subtype'])}"
            G.add_edge(sid, d_id, relation="STUDIES_DISEASE", weight=1.0)

        # Study -> Technology
        if s["technology"]:
            t_id = f"tech_{normalize(s['technology'])}"
            G.add_edge(sid, t_id, relation="USES_TECHNOLOGY", weight=1.0)

        # Study -> Author
        if s["first_author"]:
            a_id = f"author_{normalize(s['first_author'])}"
            G.add_edge(sid, a_id, relation="AUTHORED_BY", weight=1.0)

    # ── Pass 3: Cross-study similarity edges ─────────────────────────────────
    # Group by disease subtype for SHARES_DISEASE edges
    disease_groups = defaultdict(list)
    for s in studies:
        if s["disease_subtype"]:
            disease_groups[s["disease_subtype"]].append(f"study_{s['id']}")

    for disease, study_ids in disease_groups.items():
        for i, s1 in enumerate(study_ids):
            for s2 in study_ids[i+1:]:
                # Get cancer types to weight cross-cancer links higher
                ct1 = G.nodes[s1].get("cancer_type", "")
                ct2 = G.nodes[s2].get("cancer_type", "")
                cross_cancer = ct1 != ct2
                weight = 2.0 if cross_cancer else 1.0
                G.add_edge(s1, s2,
                           relation="SHARES_DISEASE",
                           disease=disease,
                           cross_cancer=cross_cancer,
                           weight=weight)
                G.add_edge(s2, s1,
                           relation="SHARES_DISEASE",
                           disease=disease,
                           cross_cancer=cross_cancer,
                           weight=weight)

    # Group by technology for SHARES_TECHNOLOGY edges
    tech_groups = defaultdict(list)
    for s in studies:
        if s["technology"]:
            tech_groups[s["technology"]].append(f"study_{s['id']}")

    for tech, study_ids in tech_groups.items():
        for i, s1 in enumerate(study_ids):
            for s2 in study_ids[i+1:]:
                G.add_edge(s1, s2, relation="SHARES_TECHNOLOGY",
                           technology=tech, weight=0.5)

    # ── Pass 4: Compute centrality metrics ───────────────────────────────────
    undirected = G.to_undirected()
    degree_centrality = nx.degree_centrality(undirected)

    for node_id, centrality in degree_centrality.items():
        G.nodes[node_id]["centrality"] = round(centrality, 4)

    return G


def graph_to_json(G: nx.MultiDiGraph) -> dict:
    """Convert graph to JSON-serializable format for the API/frontend."""
    nodes = []
    for node_id, attrs in G.nodes(data=True):
        nodes.append({
            "id": node_id,
            **attrs
        })

    edges = []
    for u, v, key, attrs in G.edges(data=True, keys=True):
        edges.append({
            "source": u,
            "target": v,
            "key": key,
            **attrs
        })

    # Compute summary stats
    study_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "Study"]
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "total_studies": len(study_nodes),
            "node_types": {
                t: sum(1 for _, d in G.nodes(data=True) if d.get("type") == t)
                for t in ["Study", "CancerType", "Disease", "Technology", "Author"]
            },
            "edge_types": {
                r: sum(1 for _, _, d in G.edges(data=True) if d.get("relation") == r)
                for r in ["BELONGS_TO", "STUDIES_DISEASE", "USES_TECHNOLOGY",
                          "AUTHORED_BY", "SHARES_DISEASE", "SHARES_TECHNOLOGY"]
            }
        }
    }


def save_graph(G: nx.MultiDiGraph, output_dir: Path):
    """Save graph in multiple formats."""
    output_dir.mkdir(exist_ok=True)

    # JSON for API
    graph_json = graph_to_json(G)
    with open(output_dir / "graph.json", "w") as f:
        json.dump(graph_json, f, indent=2)
    print(f"  Saved graph.json ({len(graph_json['nodes'])} nodes, {len(graph_json['edges'])} edges)")

    # GraphML for Gephi/Cytoscape
    # Convert MultiDiGraph to simple DiGraph for GraphML export
    simple_G = nx.DiGraph()
    for node, attrs in G.nodes(data=True):
        simple_G.add_node(node, **{k: str(v) for k, v in attrs.items()})
    for u, v, attrs in G.edges(data=True):
        if not simple_G.has_edge(u, v):
            simple_G.add_edge(u, v, **{k: str(v2) for k, v2 in attrs.items()})
    
    nx.write_graphml(simple_G, str(output_dir / "graph.graphml"))
    print(f"  Saved graph.graphml")

    return graph_json


if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent / "data"
    data_path = data_dir / "3ca_datasets.json"

    if not data_path.exists():
        print("ERROR: Run scripts/scrape_3ca.py first to generate the dataset JSON.")
        exit(1)

    print("Loading scraped data...")
    with open(data_path) as f:
        data = json.load(f)

    print(f"Building knowledge graph from {data['total_studies']} studies...")
    G = build_graph(data)

    print(f"\nGraph built:")
    print(f"  Nodes: {G.number_of_nodes()}")
    print(f"  Edges: {G.number_of_edges()}")

    print("\nSaving outputs...")
    save_graph(G, data_dir)
    print("\nDone!")
