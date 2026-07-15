# -*- coding: utf-8 -*-
"""Bonus 1 : recherche en langage naturel sur les offres et les candidats.

Réutilise le même pipeline TF-IDF que la couche 2 du moteur d'appariement (light_vec),
sans dépendre d'une correspondance exacte de mots-clés.
"""
from sklearn.metrics.pairwise import cosine_similarity


def search_offers(engine, query, top_n=10):
    q_vec = engine.light_vec.transform([query])
    sims = cosine_similarity(q_vec, engine.offers_light).ravel()
    offers = engine.offers.copy()
    offers["score"] = sims
    result = offers.sort_values("score", ascending=False).head(top_n)
    return result[["offer_id", "intitule", "entreprise", "secteur_offre", "lieu",
                   "type_contrat", "score"]].reset_index(drop=True)


def search_candidates(engine, query, top_n=10):
    q_vec = engine.light_vec.transform([query])
    candidates = engine.candidates
    cand_matrix = engine.light_vec.transform(candidates["text_light"])
    sims = cosine_similarity(q_vec, cand_matrix).ravel()
    result = candidates.copy()
    result["score"] = sims
    result = result.sort_values("score", ascending=False).head(top_n)
    return result[["candidate_id", "qualification_metier", "metier_vise", "secteur_metier",
                   "departement", "score"]].reset_index(drop=True)
