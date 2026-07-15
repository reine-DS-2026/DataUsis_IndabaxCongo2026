# -*- coding: utf-8 -*-
"""Page unique visible tant qu'aucun utilisateur n'est authentifié (cf. application/main.py)."""
import streamlit as st

from common import load_data, congo_background, fa, PRIMARY_COLOR
from auth import authenticate, create_user, AuthError, CONSEILLER_ACCESS_CODE
from cv_parser import extract_text, build_profile_from_cv
from data_prep import DEPARTEMENT_FROM_PREFIX

congo_background()
candidates, offers, ground_truth = load_data()

left, mid, right = st.columns([1, 1.5, 1])
with mid:
    st.markdown('<div style="height:4vh;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="acpe-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center;">'
        f'<div style="font-size:2.4rem;color:{PRIMARY_COLOR};margin-bottom:6px;">{fa("route")}</div>'
        f'<div class="acpe-hero-title" style="font-size:2rem;">ACPE Matcher</div>'
        f'<div style="color:{PRIMARY_COLOR}; font-weight:700; font-size:0.95rem; margin-bottom:6px;">'
        f'Agence Congolaise pour l\'Emploi</div>'
        f'<div class="acpe-hero-subtitle" style="font-size:0.85rem; margin:0 auto 18px auto;">'
        f'{len(candidates):,}'.replace(",", " ") + f' candidats · {len(offers):,}'.replace(",", " ") +
        f' offres · Hackathon IndabaX Congo 2026</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    tab_login, tab_signup = st.tabs(["🔑  Connexion", "📝  Créer un compte"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter", use_container_width=True)
        if submitted:
            u = authenticate(email, password)
            if u is None:
                st.error("Email ou mot de passe incorrect.")
            else:
                st.session_state["user"] = u
                st.rerun()

    with tab_signup:
        role_label = st.segmented_control(
            "Je suis :",
            ["👤 Demandeur", "🏢 Recruteur", "🛡️ Conseiller ACPE"],
            default="👤 Demandeur",
        )
        role_map = {
            "👤 Demandeur": "demandeur",
            "🏢 Recruteur": "recruteur",
            "🛡️ Conseiller ACPE": "conseiller",
        }
        role = role_map.get(role_label, "demandeur")

        with st.form("signup_form"):
            nom = st.text_input("Nom complet")
            email_su = st.text_input("Email", key="email_signup")
            password_su = st.text_input(
                "Mot de passe (6 caractères minimum)", type="password", key="pwd_signup"
            )
            password_confirm = st.text_input("Confirmer le mot de passe", type="password")

            candidate_id = None
            entreprise = None
            access_code = None
            cv_file = None
            structured = {}
            if role == "demandeur":
                cv_file = st.file_uploader(
                    "Votre CV (PDF, Word ou texte)", type=["pdf", "docx", "txt"],
                    help="Les compétences sont extraites automatiquement de votre CV.",
                )
                sc1, sc2 = st.columns(2)
                with sc1:
                    structured["metier_vise"] = st.text_input("Métier visé")
                    structured["secteur_metier"] = st.selectbox(
                        "Secteur recherché", sorted(candidates["secteur_metier"].unique())
                    )
                    structured["departement"] = st.selectbox(
                        "Département de résidence", sorted(set(DEPARTEMENT_FROM_PREFIX.values()))
                    )
                    structured["niveau_etude"] = st.selectbox(
                        "Niveau d'étude", sorted(candidates["niveau_etude"].unique())
                    )
                with sc2:
                    structured["objectif"] = st.selectbox("Objectif", ["Emploi", "Stage", "Formation"])
                    structured["mobilite"] = st.selectbox(
                        "Mobilité géographique", ["Oui", "Non", "Non déclaré"]
                    )
                    structured["age"] = st.number_input("Âge", min_value=16, max_value=70, value=25)
                    structured["genre"] = st.selectbox("Genre", ["Homme", "Femme"])
            elif role == "recruteur":
                entreprise = st.text_input("Nom de l'entreprise")
            else:
                access_code = st.text_input(
                    "Code d'accès Agent ACPE", type="password",
                    help="Fourni en interne par l'ACPE pour les conseillers habilités.",
                )

            submitted_su = st.form_submit_button("Créer mon compte", use_container_width=True)

        if submitted_su:
            if password_su != password_confirm:
                st.error("Les mots de passe ne correspondent pas.")
            elif role == "conseiller" and access_code != CONSEILLER_ACCESS_CODE:
                st.error("Code d'accès Agent ACPE invalide.")
            elif role == "demandeur" and cv_file is None:
                st.error("Veuillez téléverser votre CV.")
            else:
                try:
                    profil_cv = None
                    if role == "demandeur":
                        cv_text = extract_text(cv_file)
                        if not cv_text.strip():
                            st.warning(
                                "Le texte du CV n'a pas pu être extrait (fichier image ou scanné) : "
                                "le profil sera créé à partir des champs saisis uniquement."
                            )
                        profil_cv, competences = build_profile_from_cv(cv_text, structured)
                        profil_cv["cv_filename"] = cv_file.name
                    u = create_user(
                        nom=nom, email=email_su, password=password_su, role=role,
                        candidate_id=candidate_id, entreprise=entreprise, profil_cv=profil_cv,
                    )
                    st.session_state["user"] = u
                    if role == "demandeur" and profil_cv:
                        st.success(
                            f"Compte créé avec succès. Compétences détectées dans le CV : "
                            + (", ".join(competences) if competences else "aucune reconnue.")
                        )
                    else:
                        st.success("Compte créé avec succès.")
                    st.rerun()
                except AuthError as e:
                    st.error(str(e))
    st.markdown("</div>", unsafe_allow_html=True)

    st.caption(
        "Une initiative IndabaX Congo 2026 pour moderniser l'emploi national. "
        "Prototype développé dans le cadre du Hackathon IndabaX Congo 2026."
    )
