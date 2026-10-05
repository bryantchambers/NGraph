"""Deterministic, disjoint taxon-pair holdouts for transductive reconstruction."""
import numpy as np


def split_pairs(pairs, n_nodes, seed=42):
    positive = sorted({tuple(sorted(map(int, p))) for p in pairs if p[0] != p[1]})
    if len(positive) < 10:
        raise ValueError('At least ten unique positive pairs are required')
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(positive))
    n_hold = max(1, len(positive) // 10)
    parts = {
        'validation': [positive[i] for i in order[:n_hold]],
        'test': [positive[i] for i in order[n_hold:2*n_hold]],
        'train': [positive[i] for i in order[2*n_hold:]],
    }
    known = set(positive)
    negatives = [(a,b) for a in range(n_nodes) for b in range(a+1,n_nodes) if (a,b) not in known]
    if len(negatives) < 3:
        raise ValueError('Graph is saturated: insufficient true negative pairs')
    rng.shuffle(negatives)
    # Negatives are never known positive edges and partitions are disjoint.
    offset = 0
    for label in ['validation', 'test', 'train']:
        budget = min(len(parts[label]), max(1, len(negatives)//3))
        parts[label+'_negative'] = negatives[offset:offset+budget]
        offset += budget
    return {k: np.asarray(v, dtype=np.int64).reshape(-1,2) for k,v in parts.items()}
