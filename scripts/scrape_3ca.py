"""
3CA Dataset Scraper
Scrapes the Weizmann Institute 3CA website for all cancer dataset metadata
and downloads it to build the knowledge graph.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from pathlib import Path

BASE_URL = "https://www.weizmann.ac.il/sites/3CA"

CANCER_TYPES = [
    ("head-and-neck", "Head and Neck"),
    ("lung", "Lung"),
    ("liverbiliary", "Liver/Biliary"),
    ("kidney", "Kidney"),
    ("prostate", "Prostate"),
    ("sarcoma", "Sarcoma"),
    ("othermodels", "Other/Models"),
    ("brain", "Brain"),
    ("breast", "Breast"),
    ("pancreas", "Pancreas"),
    ("neuroendocrine", "Neuroendocrine"),
    ("colorectal", "Colorectal"),
    ("ovarian", "Ovarian"),
    ("skin", "Skin"),
    ("hematologic", "Hematologic"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; 3CA-Research-Scraper/1.0)"
}


def scrape_cancer_page(slug: str, cancer_name: str) -> list[dict]:
    """Scrape a single cancer type page and return list of study dicts."""
    url = f"{BASE_URL}/{slug}"
    print(f"  Scraping: {url}")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print(f"  No table found for {cancer_name}")
        return []

    rows = table.find_all("tr")
    studies = []

    for row in rows[1:]:  # skip header
        cols = row.find_all("td")
        if len(cols) < 8:
            continue

        # Title + paper link
        title_cell = cols[0]
        title_link = title_cell.find("a")
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        if title.startswith("All"):
            continue  # skip aggregate row

        paper_url = title_link.get("href", "")

        # Extract author and year from title like "Bischoff et al. 2021"
        match = re.match(r"([A-Za-z]+)\s+et al\.\s+(\d{4})", title)
        first_author = match.group(1) if match else title
        year = int(match.group(2)) if match else None

        # Data download links
        data_link = cols[1].find("a")
        metadata_link = cols[2].find("a")
        cell_types_link = cols[3].find("a")
        summary_link = cols[4].find("a")

        data_url = data_link.get("href", "") if data_link else ""
        metadata_url = metadata_link.get("href", "") if metadata_link else ""
        cell_types_url = cell_types_link.get("href", "") if cell_types_link else ""
        summary_url = summary_link.get("href", "") if summary_link else ""

        # Extract study ID from cell types URL
        study_id = None
        if cell_types_url:
            id_match = re.search(r"/(\d+)$", cell_types_url)
            study_id = id_match.group(1) if id_match else None

        # Disease / Technology / Samples / Cells
        disease = cols[5].get_text(strip=True) if len(cols) > 5 else ""
        technology = cols[6].get_text(strip=True) if len(cols) > 6 else ""
        num_samples_text = cols[7].get_text(strip=True) if len(cols) > 7 else "0"
        num_cells_text = cols[8].get_text(strip=True) if len(cols) > 8 else "0"

        try:
            num_samples = int(num_samples_text.replace(",", ""))
        except ValueError:
            num_samples = 0
        try:
            num_cells = int(num_cells_text.replace(",", ""))
        except ValueError:
            num_cells = 0

        # Optional fields
        meta_programs_link = cols[9].find("a") if len(cols) > 9 else None
        cna_link = cols[10].find("a") if len(cols) > 10 else None
        umap_link = cols[11].find("a") if len(cols) > 11 else None
        cell_cycle_link = cols[12].find("a") if len(cols) > 12 else None

        study = {
            "id": study_id or f"{first_author}_{year}_{slug}",
            "title": title,
            "first_author": first_author,
            "year": year,
            "cancer_type": cancer_name,
            "cancer_slug": slug,
            "disease_subtype": disease,
            "technology": technology,
            "num_samples": num_samples,
            "num_cells": num_cells,
            "paper_url": paper_url,
            "data_url": data_url,
            "metadata_url": metadata_url,
            "cell_types_url": cell_types_url,
            "summary_url": summary_url,
            "has_meta_programs": meta_programs_link is not None,
            "has_cna": cna_link is not None,
            "has_umap": umap_link is not None,
            "has_cell_cycle": cell_cycle_link is not None,
        }
        studies.append(study)

    return studies


def scrape_all() -> dict:
    """Scrape all cancer types and return unified dataset."""
    all_studies = []
    cancer_summary = {}

    for slug, name in CANCER_TYPES:
        print(f"\n[{name}]")
        studies = scrape_cancer_page(slug, name)
        all_studies.extend(studies)
        cancer_summary[name] = {
            "slug": slug,
            "num_studies": len(studies),
            "total_samples": sum(s["num_samples"] for s in studies),
            "total_cells": sum(s["num_cells"] for s in studies),
        }
        time.sleep(0.5)  # polite delay

    return {
        "studies": all_studies,
        "cancer_summary": cancer_summary,
        "total_studies": len(all_studies),
    }


def main():
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)

    print("=== 3CA Dataset Scraper ===\n")
    result = scrape_all()

    output_path = output_dir / "3ca_datasets.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n\n=== SUMMARY ===")
    print(f"Total studies scraped: {result['total_studies']}")
    for cancer, info in result["cancer_summary"].items():
        print(f"  {cancer}: {info['num_studies']} studies, "
              f"{info['total_cells']:,} cells, {info['total_samples']} samples")
    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()
