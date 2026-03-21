# rag_pipeline/embedder.py
"""
Embeds text chunks using a sentence-transformer model
and stores them in a FAISS index for fast similarity search.

Uses 'allenai/specter2_base' — a model trained on scientific papers,
which gives better recall for academic text than generic models.
"""

import os
import pickle
import numpy as np
from pathlib import Path

from sentence_transformers import SentenceTransformer
import faiss


MODEL_NAME  = "allenai/specter2_base"
EMBED_DIR   = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".embeddings_cache"
)


class EmbeddingStore:
    """
    Manages a FAISS index + chunk list for one study's paper.
    Persists to disk so repeated queries do not re-embed.
    """

    def __init__(self, study_id: str):
        self.study_id  = study_id
        self.store_dir = Path(EMBED_DIR) / study_id
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self.index_path  = self.store_dir / "index.faiss"
        self.chunks_path = self.store_dir / "chunks.pkl"

        self.model  = None   # lazy-loaded
        self.index  = None
        self.chunks = []

    def _load_model(self):
        if self.model is None:
            print(f"[Embedder] Loading model {MODEL_NAME} ...")
            self.model = SentenceTransformer(MODEL_NAME)

    def is_built(self) -> bool:
        return self.index_path.exists() and self.chunks_path.exists()

    def build(self, chunks: list[str]):
        """Embed chunks and build FAISS index. Saves to disk."""
        self._load_model()
        print(f"[Embedder] Embedding {len(chunks)} chunks "
              f"for study {self.study_id} ...")

        embeddings = self.model.encode(
            chunks,
            show_progress_bar=True,
            batch_size=16,
            convert_to_numpy=True,
        )
        embeddings = embeddings.astype("float32")

        # L2-normalise for cosine similarity via inner product
        faiss.normalize_L2(embeddings)

        dim         = embeddings.shape[1]
        self.index  = faiss.IndexFlatIP(dim)   # Inner Product = cosine after normalisation
        self.index.add(embeddings)
        self.chunks = chunks

        faiss.write_index(self.index, str(self.index_path))
        with open(self.chunks_path, "wb") as f:
            pickle.dump(self.chunks, f)

        print(f"[Embedder] Index built: {self.index.ntotal} vectors, dim={dim}")

    def load(self):
        """Load existing index from disk."""
        if not self.is_built():
            raise RuntimeError(
                f"No index for study {self.study_id}. Call build() first."
            )
        self.index = faiss.read_index(str(self.index_path))
        with open(self.chunks_path, "rb") as f:
            self.chunks = pickle.load(f)

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """
        Retrieve the top_k most relevant chunks for a query.
        Loads index from disk if not already loaded.
        """
        if self.index is None:
            self.load()

        self._load_model()
        q_emb = self.model.encode(
            [query],
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype("float32")
        faiss.normalize_L2(q_emb)

        scores, indices = self.index.search(q_emb, top_k)
        return [
            self.chunks[i]
            for i in indices[0]
            if 0 <= i < len(self.chunks)
        ]
