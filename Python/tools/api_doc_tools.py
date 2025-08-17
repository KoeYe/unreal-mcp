import os

from fastmcp import FastMCP 
from openai import OpenAI
from faiss import FAISS
from functools import lru_cache
from type import file

openai = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
class_db = FAISS.load_local("/data/koe/unreal-mcp/Python/database/kb_Classes.faiss")
method_db = FAISS.load_local("/data/koe/unreal-mcp/Python/database/kb_Methods.faiss")

@lru_cache(maxsize=64)
def _embedding(text: str):
    """Get text embedding from OpenAI API"""
    response = openai.Embedding.create(
        model="text-embedding-3-small",
        input=text
    )
    embedding = response.data[0].embedding
    return embedding

@lru_cache(maxsize=64)
def _recall(query: str, db: FAISS, json_file: file, top_k: int = 10):
    """Recall top-k results from the database"""
    query_embedding = _embedding(query)

    index_results, distance_results = db.similarity_search(query_embedding, k=top_k)

    with open(json_file, "r") as f:
        json_data = json.load(f)
        prompt_results = [json_data[i] for i in index_results]

    return prompt_results, distance_results

@lru_cache(maxsize=64)
def _rerank(class_results, method_results):
    """Rerank results based on embedding similarity"""
    class_embeddings = np.array([_embedding(text) for text in class_results])
    anchor_embedding = np.mean(class_embeddings, axis=0)
    
    method_embeddings = np.array([_embedding(text) for text in method_results])

    def cosine_sim(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
    
    sims = [cosine_sim(anchor_embedding, m_emb) for m_emb in method_embeddings]

    sorted_indices = np.argsort(sims)[::-1]
    reranked_methods = [method_results[i] for i in sorted_indices]

    return reranked_classes, reranked_methods

def _filter(class_results, method_results) -> tuple[list[str], list[str]]:
    """Filter results based on specific criteria"""
    filtered_classes, filtered_methods = [], []
    for clas in class_results:
        if clas.startswith("## ") and len(clas) < 400: # we give class cues max length of 400
            filtered_classes.append(clas)
    for method in method_results:
        if method.startswith("### ") and len(method) < 200: # we give method cues max length of 200
            filtered_methods.append(method)
    return filtered_classes[:1], filtered_methods[:5] # we eventually give 1 class and 5 methods

@lru_cache(maxsize=64)
def retrieval(prompt: str, class_top_k: int = 3, method_top_k: int = 10):
    """Retrieve relevant chunks based on the prompt"""
    class_prompt_results, class_distances_results = _recall(prompt, class_db, "/data/koe/unreal-mcp/Python/database/kb_Classes_chunks.jsonl", class_top_k)
    method_prompt_results, method_distances_results = _recall(prompt, method_db, "/data/koe/unreal-mcp/Python/database/kb_Methods_chunks.jsonl", method_top_k)

    class_prompt_results, method_prompt_results = _rerank(class_prompt_results, method_prompt_results)

    class_prompt_results, method_prompt_results = _filter(class_prompt_results, method_prompt_results)

    return class_prompt_results, method_prompt_results


def register_api_doc_tools(mcp: FastMCP):
    """Register API Doc tools with the MCP server."""
    @mcp.tool
    @lru_cache(maxsize=64)
    def api_doc_query(prompt: str) -> str:
        """Query the database"""
        try:
            classes_results, methods_results = retrieval(prompt)
            text_cue = f"""
            ## Class Results:
            {clas + "\n" for clas in classes_results}

            ## Method Results:
            {method + "\n" for method in methods_results}
            """
            return {"success": True, "data": text_cue}
        except Exception as e:
            return {"success": False, "error": str(e)}

