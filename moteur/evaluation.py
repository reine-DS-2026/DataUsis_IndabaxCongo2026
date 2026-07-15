# -*- coding: utf-8 -*-
"""Protocole d'évaluation (cf. Rapport_Methodologique_ACPE_IndabaX2026.docx, section 5).

Split train/validation/test réalisé par candidat (jamais par ligne) pour éviter toute
fuite via les 3 offres de vérité terrain d'un même candidat.

Rappel du plafond théorique : avec seulement 3 offres pertinentes par candidat,
Precision@5 <= 60% et Precision@10 <= 30% dans l'absolu, indépendamment du modèle.
"""
import numpy as np
import pandas as pd


def split_candidates(candidate_ids, test_size=0.2, seed=42):
    rng = np.random.RandomState(seed)
    ids = np.array(sorted(candidate_ids))
    rng.shuffle(ids)
    n_test = int(len(ids) * test_size)
    return ids[n_test:], ids[:n_test]  # train_ids, test_ids


def precision_at_k(recommended, relevant, k):
    top_k = recommended[:k]
    if len(top_k) == 0:
        return 0.0
    hits = sum(1 for o in top_k if o in relevant)
    return hits / k


def recall_at_k(recommended, relevant, k):
    if len(relevant) == 0:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for o in top_k if o in relevant)
    return hits / len(relevant)


def ndcg_at_k(recommended, relevant, k):
    top_k = recommended[:k]
    dcg = 0.0
    for i, o in enumerate(top_k):
        if o in relevant:
            dcg += 1.0 / np.log2(i + 2)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / np.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate(engine, candidate_ids, ground_truth, k_list=(5, 10)):
    gt_by_candidate = ground_truth.groupby("candidate_id")["offer_id"].apply(set).to_dict()

    metrics = {f"precision@{k}": [] for k in k_list}
    metrics.update({f"recall@{k}": [] for k in k_list})
    metrics.update({f"ndcg@{k}": [] for k in k_list})

    max_k = max(k_list)
    for cid in candidate_ids:
        relevant = gt_by_candidate.get(cid, set())
        if not relevant:
            continue
        recs = engine.recommend(cid, k=max_k)
        recommended = recs["offer_id"].tolist()
        for k in k_list:
            metrics[f"precision@{k}"].append(precision_at_k(recommended, relevant, k))
            metrics[f"recall@{k}"].append(recall_at_k(recommended, relevant, k))
            metrics[f"ndcg@{k}"].append(ndcg_at_k(recommended, relevant, k))

    return {name: float(np.mean(vals)) if vals else None for name, vals in metrics.items()}


def evaluate_baselines(engine_cls, offers, candidates, ground_truth, test_ids, k_list=(5, 10)):
    """Compare règles seules / texte seul / hybride, pour justifier empiriquement
    le choix de l'architecture (cf. section 5 du rapport méthodologique)."""
    configs = {
        "regles_seules": {"secteur_localisation": 0.6, "texte": 0.0, "structure": 0.4},
        "texte_seul": {"secteur_localisation": 0.0, "texte": 1.0, "structure": 0.0},
        "hybride": {"secteur_localisation": 0.40, "texte": 0.35, "structure": 0.25},
    }
    results = {}
    for name, weights in configs.items():
        engine = engine_cls(offers, candidates, weights=weights)
        results[name] = evaluate(engine, test_ids, ground_truth, k_list=k_list)
    return results
