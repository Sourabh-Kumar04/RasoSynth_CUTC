"""Semantic Density & Topic Coverage Visualizer.

Projects dataset instructions and responses into 2D semantic space (TF-IDF + PCA/SVD)
to visualize cluster distribution, topic balance, outlier edge cases, and synthetic redundancies.
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional
import numpy as np


def tokenize_text(text: str) -> List[str]:
    """Tokenize multilingual text into clean lowercased tokens."""
    return [w.lower() for w in re.findall(r"\w{3,}", text) if not w.isnumeric()]


def build_tfidf_matrix(texts: List[str], max_features: int = 128) -> tuple[np.ndarray, List[str]]:
    """Construct TF-IDF feature matrix and vocabulary from text collection."""
    doc_tokens = [tokenize_text(t) for t in texts]
    num_docs = max(len(texts), 1)

    # Document frequency
    df_counter = Counter()
    for tokens in doc_tokens:
        unique_tokens = set(tokens)
        df_counter.update(unique_tokens)

    # Pick top features by document frequency (ignoring ultra-rare tokens if possible)
    most_common = df_counter.most_common(max_features)
    vocab = [word for word, count in most_common]
    if not vocab:
        vocab = ["dataset", "instruction", "sample"]

    vocab_index = {w: i for i, w in enumerate(vocab)}
    vocab_size = len(vocab)

    # Compute IDF
    idf = np.zeros(vocab_size)
    for i, w in enumerate(vocab):
        count = df_counter.get(w, 0)
        idf[i] = math.log((num_docs + 1) / (count + 1)) + 1.0

    # Build TF-IDF matrix
    matrix = np.zeros((num_docs, vocab_size), dtype=np.float32)
    for row_idx, tokens in enumerate(doc_tokens):
        if not tokens:
            continue
        token_counts = Counter(tokens)
        total_tokens = len(tokens)
        for w, cnt in token_counts.items():
            if w in vocab_index:
                col_idx = vocab_index[w]
                tf = cnt / total_tokens
                matrix[row_idx, col_idx] = tf * idf[col_idx]

    # L2 normalize rows
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    return matrix, vocab


def reduce_dimension_2d(matrix: np.ndarray) -> np.ndarray:
    """Project high-dimensional TF-IDF matrix into 2D coordinates using SVD."""
    n_samples, n_features = matrix.shape
    if n_samples == 0:
        return np.zeros((0, 2))
    if n_samples == 1:
        return np.array([[50.0, 50.0]])
    if n_features < 2:
        coords = np.zeros((n_samples, 2))
        coords[:, 0] = np.linspace(20.0, 80.0, n_samples)
        coords[:, 1] = 50.0
        return coords

    # Mean center
    centered = matrix - np.mean(matrix, axis=0)

    try:
        # SVD: matrix = U * S * Vt
        u, s, _ = np.linalg.svd(centered, full_matrices=False)
        coords = u[:, :2] * s[:2]
    except Exception:
        # Fallback to random projection if numerical SVD encounters edge singularity
        rnd = np.random.RandomState(42)
        proj = rnd.randn(n_features, 2)
        coords = np.dot(centered, proj)

    # Scale to canvas coordinates [10.0, 90.0]
    min_x, max_x = np.min(coords[:, 0]), np.max(coords[:, 0])
    min_y, max_y = np.min(coords[:, 1]), np.max(coords[:, 1])

    range_x = max_x - min_x if max_x > min_x else 1.0
    range_y = max_y - min_y if max_y > min_y else 1.0

    scaled_x = 10.0 + ((coords[:, 0] - min_x) / range_x) * 80.0
    scaled_y = 10.0 + ((coords[:, 1] - min_y) / range_y) * 80.0

    scaled = np.column_stack((scaled_x, scaled_y))
    return np.round(scaled, 2)


def run_simple_kmeans(coords: np.ndarray, k: int = 4, max_iters: int = 20) -> tuple[List[int], np.ndarray]:
    """Run lightweight, deterministic K-means clustering on 2D coordinates."""
    n_samples = len(coords)
    k = min(k, max(1, n_samples))

    if n_samples <= k:
        return list(range(n_samples)), coords.copy()

    # Deterministic seed points based on spatial quantiles
    indices = np.linspace(0, n_samples - 1, k, dtype=int)
    centroids = coords[indices].copy()

    assignments = np.zeros(n_samples, dtype=int)

    for _ in range(max_iters):
        # Distance to each centroid
        dists = np.linalg.norm(coords[:, np.newaxis, :] - centroids[np.newaxis, :, :], axis=2)
        new_assignments = np.argmin(dists, axis=1)

        if np.array_equal(new_assignments, assignments):
            break
        assignments = new_assignments

        # Update centroids
        for c in range(k):
            members = coords[assignments == c]
            if len(members) > 0:
                centroids[c] = np.mean(members, axis=0)

    return assignments.tolist(), centroids


def analyze_semantic_diversity(
    samples: List[Dict[str, Any]],
    k_clusters: int = 4,
) -> Dict[str, Any]:
    """Analyze dataset semantic density, 2D topic clusters, entropy, and outliers."""
    if not samples:
        return {
            "total_samples": 0,
            "diversity_entropy": 0.0,
            "semantic_coverage_pct": 0.0,
            "clusters": [],
            "points": [],
            "outlier_count": 0,
            "redundancy_count": 0,
        }

    texts = []
    for s in samples:
        inst = s.get("instruction", "")
        resp = s.get("response", "")
        combined = f"{inst} {resp}".strip()
        texts.append(combined if combined else "empty sample")

    # 1. TF-IDF & Vocabulary
    matrix, vocab = build_tfidf_matrix(texts, max_features=128)

    # 2. 2D Dimensionality Reduction
    coords = reduce_dimension_2d(matrix)

    # 3. K-means Clustering
    k = min(k_clusters, len(samples))
    assignments, centroids = run_simple_kmeans(coords, k=k)

    # 4. Cluster Analysis & Top Keywords
    clusters_info = []
    for c_id in range(k):
        member_indices = [i for i, a in enumerate(assignments) if a == c_id]
        count = len(member_indices)
        pct = round((count / len(samples)) * 100, 1)

        # Find top terms for this cluster
        if member_indices and len(vocab) > 0:
            cluster_weights = np.sum(matrix[member_indices], axis=0)
            top_vocab_indices = np.argsort(cluster_weights)[::-1][:4]
            top_terms = [vocab[idx] for idx in top_vocab_indices if cluster_weights[idx] > 0]
        else:
            top_terms = ["general"]

        cluster_label = " & ".join(top_terms[:2]).title() if top_terms else f"Cluster {c_id + 1}"

        cent = centroids[c_id].tolist() if c_id < len(centroids) else [50.0, 50.0]
        clusters_info.append({
            "cluster_id": c_id,
            "label": cluster_label,
            "sample_count": count,
            "percentage": pct,
            "centroid": [round(cent[0], 2), round(cent[1], 2)],
            "top_terms": top_terms,
        })

    # 5. Outlier & Redundancy Detection
    # Calculate distance of each sample from its assigned cluster centroid
    distances = []
    for i, (pt, c_id) in enumerate(zip(coords, assignments)):
        cent = centroids[c_id]
        dist = float(np.linalg.norm(pt - cent))
        distances.append(dist)

    avg_dist = float(np.mean(distances)) if distances else 0.0
    dist_threshold_outlier = avg_dist * 1.8 if avg_dist > 0 else 50.0
    dist_threshold_redundancy = avg_dist * 0.15 if avg_dist > 0 else 2.0

    points = []
    outlier_count = 0
    redundancy_count = 0

    for i, s in enumerate(samples):
        x, y = float(coords[i, 0]), float(coords[i, 1])
        c_id = assignments[i]
        d = distances[i]
        is_outlier = d > dist_threshold_outlier
        is_redundant = d < dist_threshold_redundancy

        if is_outlier:
            outlier_count += 1
        elif is_redundant:
            redundancy_count += 1

        inst_snippet = s.get("instruction", "")[:90] + ("..." if len(s.get("instruction", "")) > 90 else "")

        points.append({
            "id": s.get("id") or f"pt-{i+1}",
            "x": x,
            "y": y,
            "cluster_id": c_id,
            "cluster_label": clusters_info[c_id]["label"],
            "is_outlier": is_outlier,
            "is_redundant": is_redundant,
            "instruction_snippet": inst_snippet,
            "domain": s.get("metadata", {}).get("domain") or s.get("domain", "General"),
        })

    # 6. Diversity Entropy (Shannon Entropy normalized to [0, 1])
    probs = [c["sample_count"] / len(samples) for c in clusters_info if c["sample_count"] > 0]
    shannon_entropy = -sum(p * math.log2(p) for p in probs) if probs else 0.0
    max_entropy = math.log2(k) if k > 1 else 1.0
    normalized_entropy = round(min(1.0, max(0.0, shannon_entropy / max_entropy)), 3)

    coverage_pct = round(min(100.0, (1.0 - (outlier_count / max(len(samples), 1)) * 0.5) * 100), 1)

    return {
        "total_samples": len(samples),
        "diversity_entropy": normalized_entropy,
        "semantic_coverage_pct": coverage_pct,
        "clusters": clusters_info,
        "points": points,
        "outlier_count": outlier_count,
        "redundancy_count": redundancy_count,
    }
