from __future__ import annotations

from pathlib import Path
from typing import Any


class DreamsRunner:
    """DreaMS embedding computation and spectral library search."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_dreams(self) -> Any:
        try:
            import dreams
            return dreams
        except ImportError as exc:
            raise RuntimeError("DreaMS is not installed. Install 'dreams' via /system/packages/install.") from exc

    def _ensure_sklearn(self) -> Any:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            return cosine_similarity
        except ImportError as exc:
            raise RuntimeError("scikit-learn is required for DreaMS similarity.") from exc

    def _embedding_cache_path(self, spectra_file: Path) -> Path:
        return self.cache_dir / f"{spectra_file.stem}_embeddings.npz"

    def compute_embeddings(self, spectra_file: Path) -> tuple[Any, list[dict[str, Any]]]:
        """Compute DreaMS embeddings for an MGF/mzML file; cache to .npz."""
        dreams = self._ensure_dreams()
        cache = self._embedding_cache_path(spectra_file)
        if cache.exists():
            import numpy as np
            data = np.load(cache, allow_pickle=True)
            return data["embeddings"], data["metadata"].tolist()

        from dreams.api import dreams_embeddings
        embeddings, metadata = dreams_embeddings(str(spectra_file))
        import numpy as np
        np.savez_compressed(cache, embeddings=embeddings, metadata=metadata)
        return embeddings, metadata

    def library_search(
        self,
        query_file: Path,
        library_file: Path,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return top-k library hits per query spectrum using DreaMS embeddings."""
        q_emb, q_meta = self.compute_embeddings(query_file)
        l_emb, l_meta = self.compute_embeddings(library_file)
        cosine_similarity = self._ensure_sklearn()
        sims = cosine_similarity(q_emb, l_emb)

        results: list[dict[str, Any]] = []
        for qi, query in enumerate(q_meta):
            top_indices = sims[qi].argsort()[::-1][:top_k]
            for rank, li in enumerate(top_indices, start=1):
                hit = l_meta[li]
                results.append({
                    "feature_id": query.get("spectrum_id", f"Q{qi:04d}"),
                    "mz": query.get("precursor_mz"),
                    "rt": query.get("retention_time"),
                    "candidate_name": hit.get("compound_name") or hit.get("name"),
                    "smiles": hit.get("smiles"),
                    "inchikey": hit.get("inchikey"),
                    "dreams_score": round(float(sims[qi, li]), 4),
                    "dreams_rank": rank,
                    "annotation_source": "dreams",
                })
        return results
