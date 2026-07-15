# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px

from common import (
    load_data, load_engine, kpi_tile, chatbot_widget, top_bar,
    load_recommendations_all, load_dashboard_stats,
)
from pdf_report import generate_report
from chatbot import answer_conseiller, SUGGESTIONS_CONSEILLER

user = st.session_state["user"]
candidates, offers, ground_truth = load_data()
engine = load_engine()
stats = load_dashboard_stats()
recs_all = load_recommendations_all()

top_bar("Console décisionnelle", "shield-halved", user, extra=lambda col: (
    chatbot_widget(
        "Assistant ACPE", f"Posez une question sur les KPIs ou la géographie, {user['nom']}.",
        SUGGESTIONS_CONSEILLER, lambda q: answer_conseiller(q, stats, user["nom"]), "conseiller",
    ) if stats is not None else None
))

if stats is not None:
    st.download_button(
        "📄 Exporter le rapport en PDF", data=generate_report(stats),
        file_name=f"rapport_acpe_matcher_{pd.Timestamp.today().date()}.pdf",
        mime="application/pdf",
    )

if stats is None:
    st.warning(
        "Les statistiques précalculées ne sont pas encore disponibles. "
        "Lancez `python moteur/build_artifacts.py` pour les générer."
    )
    st.stop()

tab_kpi, tab_geo, tab_manuel = st.tabs([
    "📊 KPIs macro-économiques", "🗺️ Cartographie de l'emploi", "🛠️ Intervention manuelle",
])

with tab_kpi:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_tile("Candidats actifs", f"{stats['n_candidats']:,}".replace(",", " "), "users", "blue")
    with c2:
        kpi_tile("Offres d'emploi", f"{stats['n_offres']:,}".replace(",", " "), "briefcase", "orange")
    with c3:
        kpi_tile("Compatibilité moyenne (Top-1)", f"{stats['taux_moyen_compatibilite_top1']*100:.1f} %",
                  "bullseye", "green")
    with c4:
        kpi_tile("Offres à texte riche", stats["n_offres_texte_riche"], "file-lines", "purple")
    st.write("")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("###### Secteurs les plus représentés (offres)")
        d = pd.Series(stats["secteurs_offres_top10"]).sort_values()
        fig = px.bar(d, orientation="h", labels={"index": "", "value": "Nombre d'offres"})
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, width='stretch')
    with col2:
        st.markdown("###### Métiers les plus demandés (candidats)")
        d2 = pd.Series(stats["metiers_demandes_top10"]).sort_values()
        fig2 = px.bar(d2, orientation="h", labels={"index": "", "value": "Nombre de candidats"})
        fig2.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig2, width='stretch')

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("###### Répartition par niveau d'étude")
        d3 = pd.Series(stats["repartition_niveau_etude"])
        fig3 = px.pie(values=d3.values, names=d3.index, hole=0.4)
        fig3.update_layout(height=350)
        st.plotly_chart(fig3, width='stretch')
    with col4:
        st.markdown("###### Distribution des scores de compatibilité (Top-1 par candidat)")
        top1 = recs_all[recs_all["rank"] == 1]
        fig4 = px.histogram(top1, x="score", nbins=30)
        fig4.update_layout(height=350, xaxis_title="Score de compatibilité", yaxis_title="Nombre de candidats")
        st.plotly_chart(fig4, width='stretch')

with tab_geo:
    st.markdown("Analyse géographique croisant la localisation des candidats (département déduit du "
                "Matricule) et celle des offres, pour identifier les zones de tension ou de forte "
                "employabilité.")
    dep_cand = pd.Series(stats["repartition_candidats_par_departement"], name="Candidats")
    dep_off = pd.Series(stats["repartition_offres_par_departement"], name="Offres")
    dep_df = pd.concat([dep_cand, dep_off], axis=1).fillna(0).sort_values("Candidats", ascending=False)
    cand_safe = dep_df["Candidats"].astype(float).replace(0, float("nan"))
    dep_df["Offres pour 100 candidats"] = (dep_df["Offres"].astype(float) / cand_safe * 100).round(1)

    fig = px.bar(dep_df.reset_index().melt(id_vars="index", value_vars=["Candidats", "Offres"]),
                 x="index", y="value", color="variable", barmode="group",
                 labels={"index": "Département", "value": "Nombre", "variable": ""})
    fig.update_layout(height=420)
    st.plotly_chart(fig, width='stretch')

    st.markdown("###### Tension emploi/candidats par département")
    st.caption("Un ratio faible indique une zone où l'offre est rare par rapport au nombre de candidats "
               "(zone de tension) ; un ratio élevé indique une zone de forte employabilité relative.")
    st.dataframe(dep_df, width='stretch')

with tab_manuel:
    st.markdown("Outil de contrôle global et de forçage manuel de recommandation pour les entretiens "
                "physiques avec les usagers.")
    col1, col2 = st.columns(2)
    with col1:
        candidate_id = st.selectbox("Candidat", candidates["candidate_id"].tolist(), key="manuel_cand")
    with col2:
        offer_id = st.selectbox("Offre", offers["offer_id"].tolist(), key="manuel_offer")

    cand_row = candidates.loc[candidates["candidate_id"] == candidate_id].iloc[0]
    offer_row = offers.loc[offers["offer_id"] == offer_id].iloc[0]

    recs = engine.recommend(candidate_id, k=10)
    already_recommended = offer_id in recs["offer_id"].values

    if already_recommended:
        rank = int(recs.loc[recs.offer_id == offer_id, "rank"].values[0])
        st.success(f"Cette offre est déjà recommandée au rang {rank} pour ce candidat.")
    else:
        st.warning("Cette offre n'apparaît pas dans le Top-10 automatique de ce candidat.")

    if st.button("Générer un rapport de suivi pour l'entretien"):
        st.markdown("###### Rapport de suivi")
        st.write({
            "Candidat": candidate_id,
            "Profil": cand_row["qualification_metier"],
            "Département": cand_row["departement"],
            "Offre": f"{offer_row['intitule']} — {offer_row['entreprise']}",
            "Lieu de l'offre": offer_row["lieu"],
            "Recommandation automatique": "Oui" if already_recommended else "Forcée manuellement par le conseiller",
        })
