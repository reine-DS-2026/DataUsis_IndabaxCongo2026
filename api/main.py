# -*- coding: utf-8 -*-
"""API REST du moteur ACPE Matcher, destinée aux chercheurs (accès programmatique aux
prédictions, cf. profil "Chercheur"/"Conseiller" de l'architecture applicative).

Lancer avec : uvicorn api.main:app --port 8000
Documentation interactive auto-générée : http://localhost:8000/docs
"""
import os
import sys
import json
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "moteur"))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io

from data_prep import build_all
from matching import MatchingEngine, DEFAULT_WEIGHTS
from search import search_offers, search_candidates

DONNEES_GENEREES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "donnees_generees")

app = FastAPI(
    title="ACPE Matcher API",
    description="API REST du système intelligent d'appariement demandeurs d'emploi / offres "
                "d'emploi de l'ACPE — Hackathon IndabaX Congo 2026.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_state = {}


@app.on_event("startup")
def startup():
    candidates, offers, ground_truth = build_all(cache=True)
    engine = MatchingEngine(offers, candidates, weights=DEFAULT_WEIGHTS)
    _state["candidates"] = candidates
    _state["offers"] = offers
    _state["ground_truth"] = ground_truth
    _state["engine"] = engine


@app.get("/")
def root():
    return {
        "name": "ACPE Matcher API",
        "docs": "/docs",
        "endpoints": [
            "/api/candidates/{candidate_id}/recommendations",
            "/api/offers/{offer_id}/candidates",
            "/api/search/offers", "/api/search/candidates",
            "/api/stats", "/api/evaluation", "/api/export/csv",
        ],
    }


@app.get("/api/candidates/{candidate_id}/recommendations")
def get_recommendations(candidate_id: str, k: int = Query(10, ge=1, le=50)):
    candidates = _state["candidates"]
    if candidate_id not in candidates["candidate_id"].values:
        raise HTTPException(status_code=404, detail=f"Candidat inconnu : {candidate_id}")
    recs = _state["engine"].recommend(candidate_id, k=k)
    return json.loads(recs.to_json(orient="records"))


@app.get("/api/offers/{offer_id}/candidates")
def get_candidates_for_offer(offer_id: str, k: int = Query(10, ge=1, le=50)):
    offers = _state["offers"]
    match = offers.loc[offers["offer_id"] == offer_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Offre inconnue : {offer_id}")
    offer_row = match.iloc[0]
    recs = _state["engine"].recommend_candidates(offer_row, k=k)
    return json.loads(recs.to_json(orient="records"))


@app.get("/api/search/offers")
def api_search_offers(q: str, top_n: int = Query(10, ge=1, le=50)):
    results = search_offers(_state["engine"], q, top_n=top_n)
    return json.loads(results.to_json(orient="records"))


@app.get("/api/search/candidates")
def api_search_candidates(q: str, top_n: int = Query(10, ge=1, le=50)):
    results = search_candidates(_state["engine"], q, top_n=top_n)
    return json.loads(results.to_json(orient="records"))


@app.get("/api/stats")
def get_stats():
    path = os.path.join(DONNEES_GENEREES_DIR, "dashboard_stats.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Statistiques non précalculées.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/evaluation")
def get_evaluation():
    path = os.path.join(DONNEES_GENEREES_DIR, "evaluation_final.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Évaluation non précalculée.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/export/csv")
def export_csv(candidate_id: Optional[str] = None):
    path = os.path.join(DONNEES_GENEREES_DIR, "recommendations_export.csv")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Recommandations non précalculées. "
                                                       "Lancez moteur/build_artifacts.py.")
    df = pd.read_csv(path)
    if candidate_id:
        df = df[df["candidate_id"] == candidate_id]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Candidat inconnu : {candidate_id}")
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=recommendations.csv"},
    )
