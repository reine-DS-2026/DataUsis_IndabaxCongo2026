# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from common import load_data, load_engine, kpi_tile, chatbot_widget, top_bar
from data_prep import NON_RENSEIGNE, VILLE_TO_DEPARTEMENT, norm_upper
from search import search_candidates
from chatbot import answer_recruteur, SUGGESTIONS_RECRUTEUR

user = st.session_state["user"]
candidates, offers, ground_truth = load_data()
engine = load_engine()

top_bar("Espace recruteur", "building", user)
st.caption(f"Entreprise : {user['entreprise']}")

tab_existing, tab_new, tab_search = st.tabs([
    "📋 Offres publiées", "📝 Publier une nouvelle offre", "🔎 Recherche de talents",
])

with tab_existing:
    st.markdown("Sélectionnez une offre déjà publiée par l'ACPE pour voir les meilleurs candidats.")
    secteurs = sorted(offers["secteur_offre"].unique())
    secteur_filter = st.selectbox("Filtrer par secteur", ["(tous)"] + secteurs)
    subset = offers if secteur_filter == "(tous)" else offers[offers["secteur_offre"] == secteur_filter]
    offer_id = st.selectbox(
        "Offre", subset["offer_id"].tolist(),
        format_func=lambda oid: f"{oid} — {subset.loc[subset.offer_id==oid, 'intitule'].values[0]}",
    )
    offer_row = offers.loc[offers["offer_id"] == offer_id].iloc[0]

    st.markdown(f"**{offer_row['intitule']}** — {offer_row['entreprise']} · {offer_row['lieu']} · "
                f"{offer_row['type_contrat']}")

    k = st.radio("Nombre de candidats", [5, 10], horizontal=True, index=1, key="k_existing")
    recs = engine.recommend_candidates(offer_row, k=k)
    display = recs[["rank", "candidate_id", "qualification_metier", "metier_vise", "secteur_metier",
                     "departement", "score_final"]].copy()
    display["score_final"] = (display["score_final"] * 100).round(1).astype(str) + " %"
    display = display.rename(columns={
        "rank": "Rang", "candidate_id": "Candidat (anonymisé)", "qualification_metier": "Qualification",
        "metier_vise": "Métier visé", "secteur_metier": "Secteur", "departement": "Département",
        "score_final": "Compatibilité",
    })
    st.dataframe(display, width='stretch', hide_index=True)

    st.markdown("##### Fiche d'évaluation détaillée")
    cand_choice = st.selectbox("Candidat", recs["candidate_id"].tolist(), key="cand_choice_existing")
    row = recs.loc[recs["candidate_id"] == cand_choice].iloc[0]
    e1, e2, e3 = st.columns(3)
    with e1:
        kpi_tile("Secteur / localisation", f"{row['score_secteur_localisation']*100:.0f}%", "🧭", "green")
    with e2:
        kpi_tile("Texte (qualifications)", f"{row['score_texte']*100:.0f}%", "📝", "blue")
    with e3:
        kpi_tile("Structure (contrat)", f"{row['score_structure']*100:.0f}%", "📄", "orange")
    terms = engine.explain_terms(cand_choice, offer_id)
    if terms:
        st.caption("Termes ayant le plus contribué : " + ", ".join(f"**{t}**" for t, _ in terms))

    st.write("")
    chatbot_widget(
        "Assistant ACPE", f"Posez une question sur les candidats de « {offer_row['intitule']} ».",
        SUGGESTIONS_RECRUTEUR, lambda q: answer_recruteur(q, offer_row, recs, engine), "recruteur",
    )

with tab_new:
    st.markdown("Formulaire guidé — saisissez les critères, la compatibilité est estimée en temps réel "
                "sur l'ensemble de la base candidats (aucune sauvegarde, aperçu uniquement).")
    with st.form("new_offer_form"):
        colA, colB = st.columns(2)
        with colA:
            intitule = st.text_input("Intitulé du poste", placeholder="Ex: Développeur Python")
            secteur = st.selectbox("Secteur d'activité", sorted(offers["secteur_offre"].unique()))
            lieu = st.text_input("Lieu", placeholder="Ex: Brazzaville")
            type_contrat = st.selectbox("Type de contrat", sorted(offers["type_contrat"].unique()))
        with colB:
            groupe_contrat = st.selectbox("Groupe de contrat", sorted(offers["groupe_contrat"].unique()))
            description = st.text_area("Description du poste", height=80)
            profil = st.text_area("Profil recherché", height=80)
            competences = st.text_input("Compétences requises (séparées par des virgules)")
        submitted = st.form_submit_button("Estimer les meilleurs candidats")

    if submitted:
        text_rich = " ".join(filter(None, [description, profil, competences])).strip()
        departement_offre = VILLE_TO_DEPARTEMENT.get(norm_upper(lieu), lieu or "Non déterminé")
        offer_preview = {
            "text_light": intitule or "",
            "secteur_offre": secteur,
            "departement_offre": departement_offre,
            "groupe_contrat": groupe_contrat,
            "has_rich_text": bool(text_rich),
            "text_rich": text_rich,
        }
        recs = engine.recommend_candidates(offer_preview, k=10)
        display = recs[["rank", "candidate_id", "qualification_metier", "metier_vise", "secteur_metier",
                         "departement", "score_final"]].copy()
        display["score_final"] = (display["score_final"] * 100).round(1).astype(str) + " %"
        display = display.rename(columns={
            "rank": "Rang", "candidate_id": "Candidat (anonymisé)", "qualification_metier": "Qualification",
            "metier_vise": "Métier visé", "secteur_metier": "Secteur", "departement": "Département",
            "score_final": "Compatibilité",
        })
        st.success(f"{len(recs)} candidats potentiels identifiés.")
        st.dataframe(display, width='stretch', hide_index=True)

with tab_search:
    st.markdown("Recherche sémantique de candidats en langage naturel, en dehors des recommandations "
                "automatisées du système.")
    query = st.text_input(
        "Décrivez le profil recherché", placeholder="Ex: candidat en comptabilité disponible immédiatement",
        key="recruteur_search",
    )
    if query:
        results = search_candidates(engine, query, top_n=10)
        results_display = results.copy()
        results_display["score"] = (results_display["score"] * 100).round(1).astype(str) + " %"
        st.dataframe(results_display.rename(columns={
            "candidate_id": "Candidat (anonymisé)", "qualification_metier": "Qualification",
            "metier_vise": "Métier visé", "secteur_metier": "Secteur", "departement": "Département",
            "score": "Pertinence",
        }), width='stretch', hide_index=True)
