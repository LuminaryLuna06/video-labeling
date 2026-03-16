import os
import pickle
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import faiss
import numpy as np

from config import Config


_store_lock = threading.Lock()
_faiss_index = None
_faiss_id_map: List[Dict[str, Any]] = []
_initialized = False


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def init_vector_store(db):
    global _initialized, _faiss_index, _faiss_id_map
    with _store_lock:
        if _initialized:
            return

        os.makedirs(os.path.dirname(Config.FAISS_INDEX_PATH), exist_ok=True)

        if os.path.exists(Config.FAISS_INDEX_PATH) and os.path.exists(Config.FAISS_MAP_PATH):
            _faiss_index = faiss.read_index(Config.FAISS_INDEX_PATH)
            with open(Config.FAISS_MAP_PATH, 'rb') as f:
                _faiss_id_map = pickle.load(f)
        else:
            _faiss_index = faiss.IndexFlatIP(Config.EMBEDDING_DIM)
            _faiss_id_map = []

        db.embeddings.create_index([('entity_id', 1), ('entity_type', 1)], unique=True)
        db.embeddings.create_index('entity_type')
        _initialized = True


def save_vector_store():
    with _store_lock:
        if _faiss_index is None:
            return
        faiss.write_index(_faiss_index, Config.FAISS_INDEX_PATH)
        with open(Config.FAISS_MAP_PATH, 'wb') as f:
            pickle.dump(_faiss_id_map, f)


def upsert_embedding(
    db,
    entity_id: str,
    entity_type: str,
    embedding: List[float],
    metadata: Optional[Dict[str, Any]] = None,
):
    global _faiss_index, _faiss_id_map

    if _faiss_index is None:
        init_vector_store(db)

    vec = np.asarray(embedding, dtype=np.float32)
    if vec.size != Config.EMBEDDING_DIM:
        raise ValueError(f'Invalid embedding dimension {vec.size}, expected {Config.EMBEDDING_DIM}')
    vec = _normalize(vec)

    now = datetime.now(timezone.utc)
    payload = {
        'entity_id': entity_id,
        'entity_type': entity_type,
        'embedding': vec.tolist(),
        'metadata': metadata or {},
        'updated_at': now,
    }

    existing = db.embeddings.find_one({'entity_id': entity_id, 'entity_type': entity_type})
    if existing:
        old_idx = existing.get('faiss_idx')
        if old_idx is not None and 0 <= old_idx < len(_faiss_id_map):
            _faiss_id_map[old_idx]['deleted'] = True

    with _store_lock:
        _faiss_index.add(vec.reshape(1, -1))
        faiss_idx = len(_faiss_id_map)
        _faiss_id_map.append({
            'entity_id': entity_id,
            'entity_type': entity_type,
            'metadata': metadata or {},
            'deleted': False,
        })

    payload['faiss_idx'] = faiss_idx
    payload['created_at'] = existing.get('created_at', now) if existing else now

    # Remove created_at from $set payload so it doesn't conflict with $setOnInsert
    set_payload = {k: v for k, v in payload.items() if k != 'created_at'}
    db.embeddings.update_one(
        {'entity_id': entity_id, 'entity_type': entity_type},
        {'$set': set_payload, '$setOnInsert': {'created_at': now}},
        upsert=True,
    )

    if _faiss_index.ntotal % 100 == 0:
        save_vector_store()

    return faiss_idx


def search_embeddings(
    db,
    query_embedding: List[float],
    top_k: int = 20,
    entity_types: Optional[List[str]] = None,
):
    if _faiss_index is None or _faiss_index.ntotal == 0:
        return []

    q = np.asarray(query_embedding, dtype=np.float32)
    q = _normalize(q)

    k = min(max(top_k * 4, top_k), _faiss_index.ntotal)
    distances, indices = _faiss_index.search(q.reshape(1, -1), k)

    results = []
    for score, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(_faiss_id_map):
            continue
        item = _faiss_id_map[idx]
        if item.get('deleted'):
            continue
        if entity_types and item.get('entity_type') not in entity_types:
            continue

        results.append({
            'entity_id': item['entity_id'],
            'entity_type': item['entity_type'],
            'score': float(score),
            'metadata': item.get('metadata', {}),
            'faiss_idx': int(idx),
        })
        if len(results) >= top_k:
            break

    return results


def get_index_stats():
    if _faiss_index is None:
        return {
            'total_vectors': 0,
            'dimension': Config.EMBEDDING_DIM,
            'id_map_size': 0,
            'by_type': {},
        }

    by_type: Dict[str, int] = {}
    for item in _faiss_id_map:
        if item.get('deleted'):
            continue
        et = item.get('entity_type', 'unknown')
        by_type[et] = by_type.get(et, 0) + 1

    return {
        'total_vectors': int(_faiss_index.ntotal),
        'dimension': Config.EMBEDDING_DIM,
        'id_map_size': len(_faiss_id_map),
        'by_type': by_type,
    }


def rebuild_from_mongo(db):
    global _faiss_index, _faiss_id_map

    _faiss_index = faiss.IndexFlatIP(Config.EMBEDDING_DIM)
    _faiss_id_map = []

    count = 0
    for doc in db.embeddings.find({}):
        vec = np.asarray(doc.get('embedding', []), dtype=np.float32)
        if vec.size != Config.EMBEDDING_DIM:
            continue
        vec = _normalize(vec)
        _faiss_index.add(vec.reshape(1, -1))
        _faiss_id_map.append({
            'entity_id': doc['entity_id'],
            'entity_type': doc['entity_type'],
            'metadata': doc.get('metadata', {}),
            'deleted': False,
        })
        db.embeddings.update_one({'_id': doc['_id']}, {'$set': {'faiss_idx': len(_faiss_id_map) - 1}})
        count += 1

    save_vector_store()
    return count
