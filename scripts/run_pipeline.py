"""
3CA Knowledge Graph - Full Pipeline Runner

Runs the complete pipeline:
1. Scrape 3CA website for dataset metadata
2. Build the knowledge graph
3. Save outputs (JSON, GraphML)
"""

import sys
import json
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.scrape_3ca import scrape_all
from scripts.generate_seed_data import generate_seed_data
from backend.graph_builder import build_graph, save_graph


def run_pipeline(skip_scrape: bool = False, use_seed: bool = False):
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    datasets_path = data_dir / "3ca_datasets.json"

    print("=" * 60)
    print("  3CA Knowledge Graph Pipeline")
    print("=" * 60)

    # ── Step 1: Scrape ────────────────────────────────────────────
    if skip_scrape and datasets_path.exists():
        print("\n[Step 1] Skipping scrape (--skip-scrape flag set)")
        with open(datasets_path) as f:
            data = json.load(f)
        print(f"  Loaded {data['total_studies']} studies from cache")
    elif use_seed:
        print("\n[Step 1] Using seed dataset (--seed flag set)")
        data = generate_seed_data()
    else:
        print("\n[Step 1] Scraping 3CA website...")
        print("  Note: If blocked (403), re-run with --seed flag")
        start = time.time()
        data = scrape_all()
        elapsed = time.time() - start

        # Fallback to seed if scraping got nothing
        if data["total_studies"] == 0:
            print("  Scraping returned 0 studies (site may block server requests)")
            print("  Falling back to seed dataset...")
            data = generate_seed_data()
        else:
            with open(datasets_path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n  ✓ Scraped {data['total_studies']} studies in {elapsed:.1f}s")
            print(f"  ✓ Saved to {datasets_path}")

    # ── Step 2: Build Graph ───────────────────────────────────────
    print("\n[Step 2] Building knowledge graph...")
    start = time.time()
    G = build_graph(data)
    elapsed = time.time() - start

    print(f"  ✓ Graph built in {elapsed:.2f}s")
    print(f"  ✓ Nodes: {G.number_of_nodes()}")
    print(f"  ✓ Edges: {G.number_of_edges()}")

    # Node type breakdown
    from collections import Counter
    type_counts = Counter(d.get("type", "?") for _, d in G.nodes(data=True))
    for t, c in type_counts.items():
        print(f"     {t}: {c}")

    # ── Step 3: Save Outputs ──────────────────────────────────────
    print("\n[Step 3] Saving outputs...")
    graph_json = save_graph(G, data_dir)

    print("\n" + "=" * 60)
    print("  Pipeline Complete!")
    print("=" * 60)
    print(f"\n  Graph JSON: {data_dir / 'graph.json'}")
    print(f"  GraphML:    {data_dir / 'graph.graphml'}")
    print(f"  Datasets:   {datasets_path}")
    print(f"\n  Edge types:")
    for rel, count in graph_json["stats"]["edge_types"].items():
        print(f"    {rel}: {count}")

    print("\n  To start the API server:")
    print("    uvicorn backend.main:app --reload --port 8000")
    print("\n  Then open: http://localhost:8000")
    print("  API docs:  http://localhost:8000/docs")


if __name__ == "__main__":
    skip = "--skip-scrape" in sys.argv
    seed = "--seed" in sys.argv
    run_pipeline(skip_scrape=skip, use_seed=seed)
