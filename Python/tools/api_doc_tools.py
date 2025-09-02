import os
import json

import faiss
import logging

import numpy as np
from fastmcp import FastMCP 
from openai import OpenAI
from functools import lru_cache


openai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
class_db = faiss.read_index("/home/rwang/coding-agent/UnrealEngine/unreal_mcp/Database/kb_Classes.faiss")
method_db = faiss.read_index("/home/rwang/coding-agent/UnrealEngine/unreal_mcp/Database/kb_Methods.faiss")

# Get logger
logger = logging.getLogger("UnrealMCP")

@lru_cache(maxsize=64)
def _embedding(text: str):
    """Get text embedding from OpenAI API"""
    logger.info(f"Getting embedding for text: {text}")
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    embedding = response.data[0].embedding
    logger.debug(f"Embedding length: {len(embedding)}")
    logger.debug(f"Embedding: {embedding}")
    return np.array(embedding)

@lru_cache(maxsize=64)
def _recall(query: str, db, json_file, top_k: int = 10):
    """Recall top-k results from the database"""
    logger.info(f"Recalling top {top_k} results for query: {query}")
    query_embedding = _embedding(query).reshape(1, -1)

    distance_results, index_results = db.search(query_embedding, k=top_k)

    logger.info(f"Index results: {index_results}")
    logger.info(f"Distance results: {distance_results}")

    index_results = index_results[0].astype(int)

    with open(json_file, "r") as f:
        json_data = json.load(f)
        prompt_results = [json_data[i] for i in index_results if i != -1]

    return prompt_results, distance_results[0]

# TODO: try Qwen3-reranker-8B here
def _rerank(class_results, method_results):
    """Rerank results based on embedding similarity"""
    logger.info("Reranking results...")
    class_embeddings = np.array([_embedding(text) for text in class_results])
    anchor_embedding = np.mean(class_embeddings, axis=0)
    
    method_embeddings = np.array([_embedding(text) for text in method_results])

    def cosine_sim(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
    
    sims = [cosine_sim(anchor_embedding, m_emb) for m_emb in method_embeddings]

    sorted_indices = np.argsort(sims)[::-1]
    reranked_methods = [method_results[i] for i in sorted_indices]

    reranked_classes = class_results

    return reranked_classes, reranked_methods

def _filter(class_results, method_results) -> tuple[list[str], list[str]]:
    """Filter results based on specific criteria"""
    logger.info("Filtering results...")
    filtered_classes, filtered_methods = [], []
    filtered_classes_num, filtered_methods_num = 0, 0
    for clas in class_results:
        if clas.startswith("## ") and len(clas) < 400: # we give class cues max length of 400
            filtered_classes.append(clas)
        else:
            filtered_classes_num += 1
    for method in method_results:
        if method.startswith("### ") and len(method) < 200: # we give method cues max length of 200
            filtered_methods.append(method)
        else:
            filtered_methods_num += 1
    logger.info(f"Filtered out {filtered_classes_num} classes and {filtered_methods_num} methods")
    return filtered_classes[:2], filtered_methods[:10] # we eventually give 1 class and 5 methods

@lru_cache(maxsize=64)
def retrieval(prompt: str, class_top_k: int = 3, method_top_k: int = 10):
    """Retrieve relevant chunks based on the prompt"""
    class_prompt_results, class_distances_results = _recall(prompt, class_db, "/home/rwang/coding-agent/UnrealEngine/unreal_mcp/Database/kb_Classes_chunks.jsonl", class_top_k)
    method_prompt_results, method_distances_results = _recall(prompt, method_db, "/home/rwang/coding-agent/UnrealEngine/unreal_mcp/Database/kb_Methods_chunks.jsonl", method_top_k)

    logger.info(f"Class results: {len(class_prompt_results)}")
    logger.info(f"Method results: {len(method_prompt_results)}")

    class_prompt_results, method_prompt_results = _rerank(class_prompt_results, method_prompt_results)

    logger.info(f"Reranked class results: {len(class_prompt_results)}")
    logger.info(f"Reranked method results: {len(method_prompt_results)}")

    class_prompt_results, method_prompt_results = _filter(class_prompt_results, method_prompt_results)

    logger.info(f"Filtered class results: {len(class_prompt_results)}")
    logger.info(f"Filtered method results: {len(method_prompt_results)}")

    return class_prompt_results, method_prompt_results


def register_api_doc_tools(mcp: FastMCP):
    """Register API Doc tools with the MCP server."""
    @mcp.tool()
    @lru_cache(maxsize=64)
    def api_doc_query(prompt: str) -> str:
        """Query the Unreal Python API database with the given prompt."""
        logger.info(f"Received prompt: {prompt}")
        try:
            classes_results, methods_results = retrieval(prompt)
            text_cue = f"""
            ## Class Results:
            {[f"{clas}\n" for clas in classes_results]}
            ## Method Results:
            {[f"{method}\n" for method in methods_results]}"""
            logger.info(f"Returning results: {text_cue}")
            return {"success": True, "message": text_cue}
        except Exception as e:
            logger.exception("Error occurred while querying API Doc")
            return {"success": False, "message": str(e)}