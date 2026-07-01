"""
Loads the scraped catalog and exposes a retrieve(query, k) function using
TF-IDF cosine similarity over name + description + test_type + job_levels.

Why TF-IDF and not embeddings/FAISS:
- Catalog is small (a few hundred items at most) -- TF-IDF is plenty accurate
  and has zero external dependency / API cost / cold-start latency, which
  matters under the 30s per-call timeout.
- Keeps the stack simple and easy to defend in the technical interview.
"""

import json
from pathlib import Path
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

CATALOG_PATH = Path(__file__).parent.parent / "data" / "catalog.json"


def _doc_text(item: Dict) -> str:
    parts = [
        item.get("name", ""),
        item.get("description", ""),
        item.get("test_type", ""),
        " ".join(item.get("job_levels", [])),
    ]
    return " ".join(p for p in parts if p)


class CatalogIndex:
    def __init__(self, catalog_path: Path = CATALOG_PATH):
        with open(catalog_path, "r", encoding="utf-8") as f:
            self.catalog: List[Dict] = json.load(f)
        self.texts = [_doc_text(item) for item in self.catalog]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(self.texts)

    def retrieve(self, query: str, k: int = 10) -> List[Dict]:
        """Return top-k catalog items most similar to query, each with a score."""
        if not query.strip():
            return []
        qvec = self.vectorizer.transform([query])
        sims = cosine_similarity(qvec, self.matrix).flatten()
        ranked_idx = sims.argsort()[::-1]
        results = []
        for idx in ranked_idx[:k]:
            if sims[idx] <= 0:
                continue
            item = dict(self.catalog[idx])
            item["_score"] = float(sims[idx])
            results.append(item)
        return results

    def find_by_name(self, name: str) -> Dict | None:
        name_low = name.lower().strip()
        for item in self.catalog:
            if item["name"].lower() == name_low:
                return item
        # fuzzy fallback: substring match
        for item in self.catalog:
            if name_low in item["name"].lower() or item["name"].lower() in name_low:
                return item
        return None

    def all_names(self) -> List[str]:
        return [item["name"] for item in self.catalog]


# Singleton, loaded once at process start
catalog_index = CatalogIndex()
