# -*- coding: utf-8 -*-
"""Point d'entrée unique de l'application.

Tant qu'aucun utilisateur n'est authentifié, seule la page de connexion est
enregistrée dans la navigation : c'est la seule chose visible au lancement de
l'application. Une fois connecté, seule la page correspondant au rôle de
l'utilisateur (Demandeur / Recruteur / Conseiller ACPE) devient accessible.
"""
import streamlit as st

from common import inject_style

st.set_page_config(page_title="ACPE Matcher", page_icon="🧭", layout="wide")
inject_style()

user = st.session_state.get("user")

if user is None:
    pg = st.navigation([st.Page("pages/login.py", title="Connexion")], position="hidden")
else:
    role_page = {
        "demandeur": st.Page("pages/demandeur.py", title="Espace Demandeur"),
        "recruteur": st.Page("pages/recruteur.py", title="Espace Recruteur"),
        "conseiller": st.Page("pages/conseiller.py", title="Console Conseiller"),
    }.get(user["role"])
    pg = st.navigation([role_page], position="hidden")

pg.run()
