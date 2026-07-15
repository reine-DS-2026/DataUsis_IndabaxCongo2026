# -*- coding: utf-8 -*-
import copy
import streamlit as st
import pandas as pd

from common import load_data, load_engine, kpi_tile, chatbot_widget, top_bar
from skills import skill_gap, SKILL_REFERENTIAL
from search import search_offers
from chatbot import answer_demandeur, SUGGESTIONS_DEMANDEUR

user = st.session_state["user"]
candidates, offers, ground_truth = load_data()
engine = load_engine()

# --- Construction du profil, qu'il provienne d'un Matricule existant ou d'un CV téléversé.
is_cv_profile = user.get("candidate_id") is None
if is_cv_profile:
    cand = dict(user["profil_cv"])
    cand.setdefault("diplome", "Non renseigné")
    display_id = f"Profil CV — {cand.get('cv_filename', 'sans nom')}"
else:
    candidate_id = user["candidate_id"]
    cand = candidates.loc[candidates["candidate_id"] == candidate_id].iloc[0]
    display_id = candidate_id

top_bar("Mon espace candidat", "user", user, extra=lambda col: chatbot_widget(
    "Assistant ACPE", f"Je peux expliquer vos recommandations et vos écarts de compétences, {user['nom']}.",
    SUGGESTIONS_DEMANDEUR,
    lambda q: answer_demandeur(q, cand, engine.recommend_for_profile(cand, k=10), engine, skill_gap, offers,
                                user_name=user["nom"]),
    "demandeur",
))

tab_profil, tab_recs, tab_gap, tab_search, tab_sim = st.tabs([
    "📄 Mon profil & CV", "🎯 Mes recommandations", "📊 Écarts de compétences",
    "🔎 Recherche intelligente", "🧪 Simulateur",
])

with tab_profil:
    st.markdown(f"##### {display_id}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_tile("Âge", int(cand["age"]) if pd.notna(cand.get("age")) else "N/A", "🎂", "blue")
    with c2:
        kpi_tile("Genre", cand.get("genre", "N/A"), "🧑", "purple")
    with c3:
        kpi_tile("Niveau d'étude", cand.get("niveau_etude", "N/A"), "🎓", "gold")
    with c4:
        kpi_tile("Département", cand.get("departement", "N/A"), "🗺️", "green")

    if is_cv_profile:
        st.info(f"📎 CV téléversé : **{cand.get('cv_filename', 'N/A')}**")
        competences_cv = cand.get("cv_competences") or []
        if competences_cv:
            st.success("Compétences détectées automatiquement dans le CV : " + ", ".join(competences_cv))
        else:
            st.warning("Aucune compétence du référentiel n'a été détectée dans le CV.")

    with st.expander("Détails complets du profil", expanded=False):
        st.write({
            "Qualification": cand.get("qualification_raw"),
            "Qualification métier (normalisée)": cand.get("qualification_metier"),
            "Secteur métier": cand.get("secteur_metier"),
            "Filière / Spécialité": cand.get("filiere"),
            "Métier visé": cand.get("metier_vise"),
            "Objectif": cand.get("objectif"),
            "Mobilité géographique": cand.get("mobilite"),
            "Diplôme": cand.get("diplome"),
        })

with tab_recs:
    st.subheader("Recommandations personnalisées")
    k = st.radio("Nombre de recommandations", [5, 10], horizontal=True, index=1, key="k_recs")
    recs = engine.recommend_for_profile(cand, k=k)

    display = recs[["rank", "intitule", "entreprise", "secteur_offre", "lieu", "type_contrat",
                     "score_final"]].copy()
    display["score_final"] = (display["score_final"] * 100).round(1).astype(str) + " %"
    display = display.rename(columns={
        "rank": "Rang", "intitule": "Intitulé", "entreprise": "Entreprise",
        "secteur_offre": "Secteur", "lieu": "Lieu", "type_contrat": "Contrat",
        "score_final": "Compatibilité",
    })
    st.dataframe(display, width='stretch', hide_index=True)

with tab_gap:
    st.subheader("Explicabilité et écarts de compétences")
    recs_gap = engine.recommend_for_profile(cand, k=10)
    offer_choice = st.selectbox(
        "Choisir une offre recommandée pour voir le détail",
        recs_gap["offer_id"].tolist(),
        format_func=lambda oid: f"{oid} — {recs_gap.loc[recs_gap.offer_id==oid, 'intitule'].values[0]}",
        key="offer_choice_gap",
    )
    offer_row = offers.loc[offers["offer_id"] == offer_choice].iloc[0]
    rec_row = recs_gap.loc[recs_gap["offer_id"] == offer_choice].iloc[0]

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        kpi_tile("Secteur / localisation", f"{rec_row['score_secteur_localisation']*100:.0f}%", "🧭", "green")
    with sc2:
        kpi_tile("Texte (qualifications)", f"{rec_row['score_texte']*100:.0f}%", "📝", "blue")
    with sc3:
        kpi_tile("Structure (contrat)", f"{rec_row['score_structure']*100:.0f}%", "📄", "orange")

    terms = engine.explain_terms_for_profile(cand, offer_choice)
    if terms:
        st.caption("Termes ayant le plus contribué à la similarité textuelle : " +
                   ", ".join(f"**{t}**" for t, _ in terms))

    acquises, manquantes = skill_gap(cand, offer_row)
    if acquises is None:
        st.info("Cette offre ne dispose pas de champ Compétences en texte libre : "
                "l'analyse des écarts de compétences n'est pas disponible pour cette offre "
                "(seules 143 offres sur 2 535 en disposent).")
    else:
        gc1, gc2 = st.columns(2)
        with gc1:
            st.success("✅ Compétences déjà validées : " +
                       (", ".join(acquises) if acquises else "aucune détectée"))
        with gc2:
            if manquantes:
                st.warning("⚠️ Compétences manquantes : " + ", ".join(manquantes))
            else:
                st.success("Aucune compétence manquante détectée.")

with tab_search:
    st.subheader("🔎 Recherche intelligente d'offres (langage naturel)")
    query = st.text_input(
        "Décrivez ce que vous cherchez", placeholder="Ex: développeur Python à Brazzaville"
    )
    if query:
        results = search_offers(engine, query, top_n=10)
        results_display = results.copy()
        results_display["score"] = (results_display["score"] * 100).round(1).astype(str) + " %"
        st.dataframe(results_display.rename(columns={
            "offer_id": "Réf.", "intitule": "Intitulé", "entreprise": "Entreprise",
            "secteur_offre": "Secteur", "lieu": "Lieu", "type_contrat": "Contrat", "score": "Pertinence",
        }), width='stretch', hide_index=True)

with tab_sim:
    st.subheader("🧪 Simulateur — anticiper l'impact")
    st.caption(
        "Modifiez la mobilité ou testez l'ajout de compétences pour voir leur impact sur le "
        "score de compatibilité avec une offre choisie, sans modifier le profil réel."
    )
    recs_sim = engine.recommend_for_profile(cand, k=10)
    offer_choice_sim = st.selectbox(
        "Offre de référence pour la simulation",
        recs_sim["offer_id"].tolist(),
        format_func=lambda oid: f"{oid} — {recs_sim.loc[recs_sim.offer_id==oid, 'intitule'].values[0]}",
        key="offer_choice_sim",
    )
    offer_row_sim = offers.loc[offers["offer_id"] == offer_choice_sim].iloc[0]

    sim1, sim2 = st.columns(2)
    with sim1:
        sim_mobilite = st.select_slider(
            "Mobilité géographique simulée", options=["Non", "Non déclaré", "Oui"],
            value=cand["mobilite"] if cand.get("mobilite") in ("Non", "Non déclaré", "Oui") else "Non déclaré",
        )
    with sim2:
        sim_skills = st.multiselect(
            "Compétences additionnelles à tester", SKILL_REFERENTIAL,
            help="Simule l'ajout de ces compétences au profil déclaré.",
        )

    if st.button("🔄 Calculer l'impact", type="primary"):
        baseline = engine.score_pair(cand, offer_row_sim)

        sim_cand = copy.deepcopy(cand) if isinstance(cand, dict) else cand.copy()
        sim_cand["mobilite"] = sim_mobilite
        if sim_skills:
            extra = " " + " ".join(sim_skills)
            sim_cand["text_light"] = str(sim_cand["text_light"]) + extra
            sim_cand["text_rich"] = str(sim_cand["text_rich"]) + extra
        simulated = engine.score_pair(sim_cand, offer_row_sim)

        delta = simulated["score_final"] - baseline["score_final"]
        r1, r2, r3 = st.columns(3)
        r1.metric("Score actuel", f"{baseline['score_final']*100:.1f} %")
        r2.metric("Score simulé", f"{simulated['score_final']*100:.1f} %",
                  delta=f"{delta*100:+.1f} pts")
        r3.metric("Secteur/localisation simulé", f"{simulated['score_secteur_localisation']*100:.0f} %",
                  delta=f"{(simulated['score_secteur_localisation']-baseline['score_secteur_localisation'])*100:+.1f} pts")
        if delta > 0:
            st.success("Ces changements amélioreraient la compatibilité avec cette offre.")
        elif delta < 0:
            st.warning("Ces changements réduiraient la compatibilité avec cette offre.")
        else:
            st.info("Aucun impact mesurable sur cette offre.")
