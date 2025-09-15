import os
import json
import logging
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import faiss
from fastmcp import FastMCP
from openai import OpenAI

import bm25s

# -----------------------------
# 配置 / 路径 和 logger
# -----------------------------
logger = logging.getLogger("UnrealMCP")
logging.basicConfig(level=logging.INFO)

MCP_DB_DIR = os.getenv("UNREAL_MCP_DB_DIR", "/opt/unreal-mcp/Database")
CLASSES_FAISS_PATH = os.path.join(MCP_DB_DIR, "kb_Classes.faiss")
METHODS_FAISS_PATH = os.path.join(MCP_DB_DIR, "kb_Methods.faiss")
CLASSES_JSON_PATH = os.path.join(MCP_DB_DIR, "kb_Classes_chunks.jsonl")
METHODS_JSON_PATH = os.path.join(MCP_DB_DIR, "kb_Methods_chunks.jsonl")

USE_SPARSE_RETRIEVAL = True
TOP_K_DENSE = int(os.getenv("TOP_K_DENSE", "20"))
TOP_K_SPARSE = int(os.getenv("TOP_K_SPARSE", "10"))

# -----------------------------
# 设置 OpenAI & 加载 FAISS 索引
# -----------------------------
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    class_db = faiss.read_index(CLASSES_FAISS_PATH)
    method_db = faiss.read_index(METHODS_FAISS_PATH)
    logger.info(f"Loaded FAISS indexes from {CLASSES_FAISS_PATH} and {METHODS_FAISS_PATH}")
except Exception as e:
    logger.error(f"Error loading FAISS indexes: {e}")
    raise

# -----------------------------
# 加载 JSON 文本数据
# -----------------------------
def load_json_list(path: str) -> List[str]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to load JSON from {path}: {e}")
        return []

class_json_data = load_json_list(CLASSES_JSON_PATH)
method_json_data = load_json_list(METHODS_JSON_PATH)

# -----------------------------
# 初始化稀疏检索
# -----------------------------
class_corpus: List[str] = []
method_corpus: List[str] = []
bm25_class: Optional[bm25s.BM25] = None
bm25_method: Optional[bm25s.BM25] = None

if USE_SPARSE_RETRIEVAL:
    class_corpus = class_json_data.copy()
    method_corpus = method_json_data.copy()
    class_tokens = bm25s.tokenize(class_corpus)
    method_tokens = bm25s.tokenize(method_corpus)
    bm25_class = bm25s.BM25(corpus=class_corpus)
    bm25_class.index(class_tokens)
    bm25_method = bm25s.BM25(corpus=method_corpus)
    bm25_method.index(method_tokens)
    logger.info("Initialized sparse retrievers with bm25s")

# -----------------------------
# Embedding 函数
# -----------------------------
@lru_cache(maxsize=128)
def _embedding(text: str) -> np.ndarray:
    logger.debug(f"Getting embedding for: {text[:50]}...")
    resp = openai.embeddings.create(model="text-embedding-3-small", input=text)
    return np.array(resp.data[0].embedding)

def _batch_embedding(texts: List[str]) -> np.ndarray:
    return np.vstack([_embedding(t) for t in texts])

# -----------------------------
# 检索函数 dense 和 sparse
# -----------------------------
def _recall_dense(query: str, db, json_data: List[str], top_k: int = 10) -> Tuple[List[str], List[float]]:
    query_emb = _embedding(query).reshape(1, -1)
    distances, indices = db.search(query_emb, k=top_k)
    indices = indices[0].astype(int)
    results: List[str] = []
    for idx in indices:
        if 0 <= idx < len(json_data):
            results.append(json_data[idx])
    return results, distances[0].tolist()

def _recall_sparse_bm25s(query: str, retriever: bm25s.BM25, corpus: List[str], top_k: int = 10) -> List[str]:
    query_tokens = bm25s.tokenize([query])[0]
    try:
        # 正常返回两个值
        docs, scores = retriever.retrieve(query_tokens, k=top_k)
    except Exception as e:
        logger.warning(f"sparse retrieve returned unexpected format, trying alternative: {e}")
        # fallback - 可能返回只有 docs
        docs_only = retriever.retrieve(query_tokens, k=top_k, return_as="documents")
        # 如果 docs_only 是 ndarray 或 list
        if hasattr(docs_only, "shape"):
            return docs_only[0].tolist()
        else:
            return list(docs_only)
    
    # docs, scores both present
    if hasattr(docs, "shape"):
        docs_list = docs[0].tolist()
    else:
        docs_list = list(docs)
    return docs_list

def _recall(
    query: str,
    db,
    sparse_retriever: Optional[bm25s.BM25],
    json_data: List[str],
    corpus: List[str],
    top_k_dense: int = 10,
    top_k_sparse: int = 20
) -> Tuple[List[str], List[float]]:
    dense_results, dense_distances = _recall_dense(query, db, json_data, top_k_dense)

    if USE_SPARSE_RETRIEVAL and sparse_retriever is not None:
        sparse_results = _recall_sparse_bm25s(query, sparse_retriever, corpus, top_k_sparse)
        # 去重 + 合并
        combined = dense_results.copy()
        for s in sparse_results:
            if s not in combined:
                combined.append(s)
            if len(combined) >= top_k_dense:
                break
        return combined, dense_distances
    else:
        return dense_results, dense_distances

# -----------------------------
# 排序 / 过滤
# -----------------------------
def _rerank(class_results: List[str], method_results: List[str]) -> Tuple[List[str], List[str]]:
    if not class_results or not method_results:
        return class_results, method_results

    class_embs = _batch_embedding(class_results)
    anchor_emb = np.mean(class_embs, axis=0)
    method_embs = _batch_embedding(method_results)

    sims = np.dot(method_embs, anchor_emb) / (
        np.linalg.norm(method_embs, axis=1) * np.linalg.norm(anchor_emb) + 1e-8
    )
    sorted_idx = np.argsort(sims)[::-1]
    reranked_methods = [method_results[i] for i in sorted_idx]
    return class_results, reranked_methods

def _filter(class_results: List[str], method_results: List[str]) -> Tuple[List[str], List[str]]:
    filtered_classes = [c for c in class_results if c.startswith("## ") and len(c) < 400][:2]
    filtered_methods = [m for m in method_results if m.startswith("### ") and len(m) < 200][:10]
    return filtered_classes, filtered_methods

# -----------------------------
# 主检索函数
# -----------------------------
@lru_cache(maxsize=128)
def retrieval(prompt: str, class_top_k: int = TOP_K_DENSE, method_top_k: int = TOP_K_DENSE) -> Tuple[List[str], List[str]]:
    classes, _ = _recall(prompt, class_db, bm25_class, class_json_data, class_corpus, class_top_k, TOP_K_SPARSE)
    methods, _ = _recall(prompt, method_db, bm25_method, method_json_data, method_corpus, method_top_k, TOP_K_SPARSE)
    classes, methods = _rerank(classes, methods)
    classes, methods = _filter(classes, methods)
    return classes, methods

# -----------------------------
# 注册工具
# -----------------------------
def register_api_doc_tools(mcp: FastMCP):
    @mcp.tool()
    @lru_cache(maxsize=64)
    def api_doc_query(query: Optional[str] = None, prompt: Optional[str] = None) -> Dict[str, Any]:
        text = query or prompt
        if not text:
            return {"success": False, "message": "Either 'query' or 'prompt' must be provided", "classes": [], "methods": []}
        try:
            classes, methods = retrieval(text)
            return {"success": True, "classes": classes, "methods": methods}
        except Exception as e:
            logger.exception("Error in api_doc_query")
            return {"success": False, "message": str(e), "classes": [], "methods": []}
