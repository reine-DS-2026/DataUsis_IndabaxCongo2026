# -*- coding: utf-8 -*-
"""Précalcule les recommandations Top-10 pour l'ensemble des candidats et les
statistiques du tableau de bord décisionnel, afin que l'application Streamlit
n'ait pas à tout recalculer à chaque lancement (~10 min pour 41 298 candidats)."""
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from data_prep import build_all
from matching import MatchingEngine, DEFAULT_WEIGHTS

DONNEES_GENEREES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees_generees")


def main():
    candidates, offers, ground_truth = build_all(cache=True)
    engine = MatchingEngine(offers, candidates, weights=DEFAULT_WEIGHTS)

    all_ids = candidates["candidate_id"].tolist()
    n = len(all_ids)
    t0 = time.time()
    rows = []
    for i, cid in enumerate(all_ids):
        recs = engine.recommend(cid, k=10)
        recs = recs.assign(candidate_id=cid)
        rows.append(recs[["candidate_id", "rank", "offer_id", "score_final",
                           "score_secteur_localisation", "score_texte", "score_structure"]])
        if (i + 1) % 2000 == 0:
            elapsed = time.time() - t0
            eta = elapsed / (i + 1) * (n - i - 1)
            print(f"{i+1}/{n} traités en {elapsed:.0f}s, ETA {eta/60:.1f} min", flush=True)

    all_recs = pd.concat(rows, ignore_index=True)
    all_recs = all_recs.rename(columns={"score_final": "score"})
    out_path = os.path.join(DONNEES_GENEREES, "recommendations_all.parquet")
    all_recs.to_parquet(out_path, index=False)
    print(f"\nrecommandations sauvegardées : {out_path} ({len(all_recs)} lignes) "
          f"en {(time.time()-t0)/60:.1f} min")

    # Format d'export attendu par le guide (candidate_id, rank, job_id, score).
    export_cols = all_recs.rename(columns={"offer_id": "job_id"})[
        ["candidate_id", "rank", "job_id", "score"]
    ]
    export_cols.to_csv(os.path.join(DONNEES_GENEREES, "recommendations_export.csv"), index=False)

    build_dashboard_stats(candidates, offers, all_recs)


def build_dashboard_stats(candidates, offers, all_recs):
    stats = {}
    stats["n_candidats"] = int(len(candidates))
    stats["n_offres"] = int(len(offers))
    stats["n_offres_texte_riche"] = int(offers["has_rich_text"].sum())

    stats["secteurs_offres_top10"] = (
        offers["secteur_offre"].value_counts().head(10).to_dict()
    )
    stats["metiers_demandes_top10"] = (
        candidates["metier_vise"].value_counts().head(10).to_dict()
    )
    stats["secteurs_candidats_top10"] = (
        candidates["secteur_metier"].value_counts().head(10).to_dict()
    )

    stats["taux_moyen_compatibilite"] = float(all_recs["score"].mean())
    stats["taux_moyen_compatibilite_top1"] = float(
        all_recs[all_recs["rank"] == 1]["score"].mean()
    )

    stats["repartition_candidats_par_departement"] = (
        candidates["departement"].value_counts().to_dict()
    )
    stats["repartition_offres_par_departement"] = (
        offers["departement_offre"].value_counts().to_dict()
    )

    stats["repartition_genre"] = candidates["genre"].value_counts().to_dict()
    stats["repartition_niveau_etude"] = candidates["niveau_etude"].value_counts().to_dict()
    stats["repartition_objectif"] = candidates["objectif"].value_counts().to_dict()
    stats["repartition_type_contrat_offres"] = offers["type_contrat"].value_counts().to_dict()

    stats["score_distribution"] = {
        "min": float(all_recs["score"].min()),
        "max": float(all_recs["score"].max()),
        "mean": float(all_recs["score"].mean()),
        "median": float(all_recs["score"].median()),
        "p25": float(all_recs["score"].quantile(0.25)),
        "p75": float(all_recs["score"].quantile(0.75)),
    }

    with open(os.path.join(DONNEES_GENEREES, "dashboard_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print("dashboard_stats.json sauvegardé")


if __name__ == "__main__":
    main()
