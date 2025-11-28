import json
import os
from typing import List, Tuple, Optional

import faiss
import numpy as np
from flask import current_app
from sentence_transformers import SentenceTransformer


_MODEL: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    """
    Lazy-load SentenceTransformer model.
    Đổi tên model tại đây nếu cần tùy chỉnh.
    """
    global _MODEL
    if _MODEL is None:
        model_name = current_app.config.get(
            "SEMANTIC_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        _MODEL = SentenceTransformer(model_name)
    return _MODEL


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-10, None)
    return vectors / norms


class QuestionVectorStore:
    """
    Vector store đơn giản cho câu hỏi, sử dụng FAISS + file JSON lưu mapping.

    - FAISS index lưu vector đã chuẩn hoá (Inner Product ~ cosine).
    - File JSON lưu danh sách question_id theo đúng thứ tự vector trong index.
    """

    def __init__(self):
        base_dir = current_app.config.get("VECTOR_STORE_DIR", "vector_store")
        os.makedirs(base_dir, exist_ok=True)

        self.index_path = os.path.join(base_dir, "questions.faiss")
        self.meta_path = os.path.join(base_dir, "questions_meta.json")

        self.index: Optional[faiss.IndexFlatIP] = None
        self.question_ids: List[str] = []
        self.dim: Optional[int] = None

        self._load_or_init()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_or_init(self) -> None:
        """Load index + metadata nếu có, ngược lại tạo index rỗng."""
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.question_ids = data.get("question_ids", [])
                self.dim = data.get("dim")
        else:
            self.question_ids = []
            self.dim = None

        if os.path.exists(self.index_path) and self.dim:
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = None

    def _save_meta(self) -> None:
        data = {"question_ids": self.question_ids, "dim": self.dim}
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _ensure_index(self, dim: int) -> None:
        if self.index is None:
            self.dim = dim
            self.index = faiss.IndexFlatIP(dim)
            self._save_meta()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_questions(self, items: List[Tuple[str, str]]) -> None:
        """
        Thêm danh sách câu hỏi mới vào index.

        :param items: list các tuple (question_id, question_text)
        """
        if not items:
            return

        model = _get_model()
        texts = [text for _, text in items]
        embs = model.encode(texts, convert_to_numpy=True)
        embs = _normalize(embs)

        dim = embs.shape[1]
        self._ensure_index(dim)

        self.index.add(embs)
        self.question_ids.extend([qid for qid, _ in items])

        # Persist
        faiss.write_index(self.index, self.index_path)
        self._save_meta()

    def rebuild_from_questions(self, items: List[Tuple[str, str]]) -> None:
        """
        Rebuild toàn bộ index từ danh sách câu hỏi (dùng khi sửa/xoá hàng loạt).
        """
        self.index = None
        self.question_ids = []
        self.dim = None

        if not items:
            # Ghi file rỗng
            if os.path.exists(self.index_path):
                os.remove(self.index_path)
            self._save_meta()
            return

        model = _get_model()
        texts = [text for _, text in items]
        embs = model.encode(texts, convert_to_numpy=True)
        embs = _normalize(embs)

        dim = embs.shape[1]
        self._ensure_index(dim)

        self.index.add(embs)
        self.question_ids = [qid for qid, _ in items]

        faiss.write_index(self.index, self.index_path)
        self._save_meta()

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Tìm các câu hỏi gần nhất theo ngữ nghĩa.

        :return: list (question_id, score)
        """
        if not self.index or not self.question_ids:
            return []

        model = _get_model()
        q_vec = model.encode([query], convert_to_numpy=True)
        q_vec = _normalize(q_vec)

        top_k = min(top_k, len(self.question_ids))
        scores, indices = self.index.search(q_vec, top_k)

        results: List[Tuple[str, float]] = []
        for score, idx in zip(scores[0], indices[0]):
            qid = self.question_ids[int(idx)]
            results.append((qid, float(score)))
        return results


def get_question_vector_store() -> QuestionVectorStore:
    """
    Helper để lấy instance vector store. Mỗi process có thể dùng 1 instance riêng.
    """
    return QuestionVectorStore()


