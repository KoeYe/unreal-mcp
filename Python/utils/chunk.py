import os
import ast
import openai
import numpy as np
from tqdm import tqdm
import faiss
import tiktoken 
import json

def chunk_API_file(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        code = f.read()

    CLASS_MARK = "## Class"
    METHOD_MARK  = "### Method"

    chunks = {
        "Classes": [""],
        "Methods": [""]
    }

    is_new_class_chunk = True
    is_new_method_chunk = True

    for line in tqdm(code.splitlines()):

        if len(line) == 0:
            continue

        if line.startswith("## Functions"):
            break

        is_new_class_chunk, is_new_method_chunk = [
            line.startswith(CLASS_MARK),
            line.startswith(METHOD_MARK)
        ]

        if is_new_class_chunk:
            chunks["Classes"].append(line)
        else:
            chunks["Classes"][-1] += line

        if is_new_method_chunk:
            chunks["Methods"].append(line)
        else:
            if not line.startswith(CLASS_MARK):
                chunks["Methods"][-1] += line

    return chunks

openai.api_key = os.getenv("OPENAI_API_KEY")

def embedding_chunks(chunks: list[str], batch_size=10, max_tokens=8192):
    embeddings = []
    filtered_chunks = []
    
    # 初始化tokenizer
    encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(text: str) -> int:
        return len(encoding.encode(text))
    
    def is_valid_chunk(chunk: str) -> bool:
        return count_tokens(chunk) <= max_tokens
    
    # 按 batch 处理
    for i in tqdm(range(0, len(chunks), batch_size)):
        batch = [c for c in chunks[i:i+batch_size] if c.strip()]
        if not batch:
            continue
        
        try: 
            resp = openai.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            # batch 成功，添加所有结果
            for j, c in enumerate(batch):
                embeddings.append(resp.data[j].embedding)
                filtered_chunks.append(c)
                
        except Exception as e:
            print(f"Batch failed, retrying individually")
            # batch 失败，逐个重试
            for chunk in batch:
                if not is_valid_chunk(chunk):
                    print(f"Chunk too long ({count_tokens(chunk)} tokens), skipping")
                    continue
                    
                try:
                    resp = openai.embeddings.create(
                        model="text-embedding-3-small",
                        input=[chunk]
                    )
                    embeddings.append(resp.data[0].embedding)
                    filtered_chunks.append(chunk)
                except Exception as single_e:
                    print(f"Single chunk failed, skipping: {single_e}")
                    continue

    embeddings = np.array(embeddings, dtype='float32')
    return embeddings, filtered_chunks

def inbounding_embeddings(key: str, embeddings, filtered_chunks):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings).astype("float32"))
    
    faiss.write_index(index, f"kb_{key}.faiss")

    with open(f"kb_{key}_chunks.jsonl", "w", encoding="utf-8") as f:
        json.dump(filtered_chunks, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    path = "/data/koe/ue_python_api/unreal.md"
    chunks = chunk_API_file(path)
    for k, v in chunks.items():
        print(k, len(v))

    print(chunks["Methods"][:3])
    print(chunks["Classes"][:3])

    for k, v in chunks.items():
        print(f"processing {k} with {len(v)} chunks")
        embeddings, filtered_chunks = embedding_chunks(v)

        print(f"Embeddings for {k} done, total {len(embeddings)} embeddings")
        print(f"Inbounding embeddings for {k}...")

        inbounding_embeddings(k, embeddings, filtered_chunks)
