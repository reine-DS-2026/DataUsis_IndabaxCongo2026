# -*- coding: utf-8 -*-
"""Bootstrap partagé par toutes les pages Streamlit : chemin vers moteur/, chargement
et mise en cache des données et du moteur d'appariement."""
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
MOTEUR_DIR = os.path.join(ROOT_DIR, "moteur")
DONNEES_GENEREES_DIR = os.path.join(ROOT_DIR, "donnees_generees")

if MOTEUR_DIR not in sys.path:
    sys.path.insert(0, MOTEUR_DIR)

import base64
import json
import pandas as pd
import streamlit as st

from data_prep import build_all
from matching import MatchingEngine, DEFAULT_WEIGHTS

ASSETS_DIR = os.path.join(APP_DIR, "images", "congo")


@st.cache_data(show_spinner="Chargement des données ACPE...")
def load_data():
    candidates, offers, ground_truth = build_all(cache=True)
    return candidates, offers, ground_truth


@st.cache_resource(show_spinner="Initialisation du moteur d'appariement...")
def load_engine():
    candidates, offers, _ = load_data()
    return MatchingEngine(offers, candidates, weights=DEFAULT_WEIGHTS)


@st.cache_data
def load_recommendations_all():
    path = os.path.join(DONNEES_GENEREES_DIR, "recommendations_all.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


@st.cache_data
def load_dashboard_stats():
    path = os.path.join(DONNEES_GENEREES_DIR, "dashboard_stats.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def load_evaluation():
    path = os.path.join(DONNEES_GENEREES_DIR, "evaluation_final.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


PRIMARY_COLOR = "#1F9D6E"
ACCENT_COLOR = "#E8792C"
BG_PAGE = "#FFFFFF"
BG_CARD = "#FFFFFF"
BG_CARD_LIGHT = "#F2F5F9"
BORDER = "rgba(15,23,42,0.09)"
TEXT_MUTED = "#5B6B85"

KPI_PALETTE = {
    "green": ("#1F9D6E", "rgba(31,157,110,0.10)"),
    "orange": ("#E8792C", "rgba(232,121,44,0.10)"),
    "blue": ("#2F7CE0", "rgba(47,124,224,0.10)"),
    "purple": ("#8B5CE0", "rgba(139,92,224,0.10)"),
    "red": ("#E0524F", "rgba(224,82,79,0.10)"),
    "gold": ("#D6A419", "rgba(214,164,25,0.10)"),
}

# Icônes Font Awesome (fa-solid) associées aux emoji historiques, pour compatibilité
# des appels existants tout en migrant l'affichage vers Font Awesome.
FA_ICONS = {
    "👥": "users", "💼": "briefcase", "📝": "file-lines", "🗺️": "map-location-dot",
    "🎂": "cake-candles", "🧑": "user", "🎓": "graduation-cap", "🧭": "compass",
    "📄": "file-contract", "🎯": "bullseye", "📊": "chart-column", "🛡️": "shield-halved",
    "🏢": "building", "👤": "user", "🔑": "key", "🆕": "user-plus", "🔎": "magnifying-glass",
    "🧪": "flask", "🔌": "plug", "🛠️": "screwdriver-wrench", "💬": "comment-dots",
}


def fa(icon, size=None):
    """Rend une icône Font Awesome. Accepte un nom fa (ex: 'users') ou, pour compatibilité,
    un emoji déjà utilisé ailleurs dans le code (converti automatiquement)."""
    name = FA_ICONS.get(icon, icon)
    style = f' style="font-size:{size};"' if size else ""
    return f'<i class="fa-solid fa-{name}"{style}></i>'


def inject_style():
    st.markdown(
        """
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
              rel="stylesheet">
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"], .stApp, .stMarkdown, p, span, div, button, input, textarea, label {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        }}

        .stApp {{
            background:
                radial-gradient(1200px 500px at 15% -10%, rgba(31,157,110,0.06), transparent 60%),
                radial-gradient(1000px 500px at 100% 0%, rgba(232,121,44,0.05), transparent 60%),
                {BG_PAGE};
        }}
        [data-testid="stSidebar"] {{
            background: {BG_CARD_LIGHT};
            border-right: 1px solid {BORDER};
        }}

        .acpe-badge {{
            display: inline-block; padding: 4px 14px; border-radius: 999px;
            background: linear-gradient(90deg, rgba(31,157,110,0.12), rgba(232,121,44,0.12));
            border: 1px solid rgba(31,157,110,0.35);
            color: {PRIMARY_COLOR}; font-weight: 700; letter-spacing: 0.04em;
            font-size: 0.72rem; margin-bottom: 14px; text-transform: uppercase;
        }}

        .acpe-hero-title {{
            font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin-bottom: 4px;
            background: linear-gradient(90deg, #1B2430 25%, {PRIMARY_COLOR} 100%);
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }}
        .acpe-hero-subtitle {{
            color: {TEXT_MUTED}; font-size: 1.02rem; max-width: 640px; margin-bottom: 6px;
        }}

        .acpe-card {{
            border: 1px solid {BORDER}; border-radius: 20px; background: {BG_CARD};
            padding: 30px 34px; margin-bottom: 14px;
            box-shadow: 0 20px 45px rgba(15,23,42,0.12);
        }}

        .kpi-tile {{
            border-radius: 16px; padding: 18px 20px; border: 1px solid {BORDER};
            border-left: 4px solid currentColor;
            display: flex; flex-direction: column; gap: 6px; height: 100%;
            box-shadow: 0 4px 14px rgba(15,23,42,0.04);
            transition: transform 0.12s ease-in-out;
        }}
        .kpi-tile:hover {{ transform: translateY(-2px); }}
        .kpi-tile .kpi-icon {{ font-size: 1.3rem; }}
        .kpi-tile .kpi-value {{ font-size: 1.9rem; font-weight: 800; line-height: 1; }}
        .kpi-tile .kpi-label {{ color: {TEXT_MUTED}; font-size: 0.82rem; font-weight: 600; }}

        /* Onglets */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px; background: {BG_CARD_LIGHT}; padding: 5px; border-radius: 999px;
            border: 1px solid {BORDER}; width: fit-content;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 999px !important; padding: 8px 20px; font-weight: 600;
            background: transparent; color: {TEXT_MUTED};
        }}
        .stTabs [aria-selected="true"] {{
            background: {PRIMARY_COLOR} !important; color: #FFFFFF !important;
            border-bottom: none !important; box-shadow: 0 3px 10px rgba(31,157,110,0.35);
        }}
        .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

        /* Boutons */
        .stButton > button, .stFormSubmitButton > button {{
            border-radius: 10px; font-weight: 700; border: none;
            background: linear-gradient(90deg, {PRIMARY_COLOR}, #17B87F);
            color: #FFFFFF; transition: transform 0.08s ease-in-out;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{ transform: translateY(-1px); }}

        .stDownloadButton > button {{
            border-radius: 10px; font-weight: 700; border: none;
            background: linear-gradient(90deg, {ACCENT_COLOR}, #F2A65A); color: #FFFFFF;
        }}

        [data-testid="stMetric"] {{
            background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 14px;
            padding: 14px 16px; box-shadow: 0 4px 14px rgba(15,23,42,0.04);
        }}

        .acpe-chat-bubble {{
            border-radius: 14px; background: {BG_CARD_LIGHT}; border: 1px solid {BORDER};
            padding: 10px 14px; margin-bottom: 8px; color: #1B2430;
        }}
        .acpe-chat-bubble.user {{ background: rgba(31,157,110,0.08); border-color: rgba(31,157,110,0.25); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_tile(label, value, icon="chart-column", color="green"):
    fg, bg = KPI_PALETTE.get(color, KPI_PALETTE["green"])
    st.markdown(
        f"""
        <div class="kpi-tile" style="background:{bg}; border-color:{fg}33;">
            <div class="kpi-icon" style="color:{fg};">{fa(icon)}</div>
            <div class="kpi-value" style="color:{fg};">{value}</div>
            <div class="kpi-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


ROLE_LABELS = {"demandeur": "Demandeur", "recruteur": "Recruteur", "conseiller": "Conseiller ACPE"}


def top_bar(title, icon, user, extra=None):
    """Barre supérieure façon SaaS : icône + titre à gauche, contenu optionnel au
    centre (ex: chatbot), badge de rôle + nom + déconnexion à droite."""
    col_title, col_extra, col_user = st.columns([4, 1.4, 2])
    with col_title:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:1.6rem;color:{PRIMARY_COLOR};">{fa(icon)}</span>'
            f'<span class="acpe-hero-title" style="font-size:1.7rem;">{title}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_extra:
        if extra is not None:
            extra(col_extra)
    with col_user:
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; justify-content:flex-end; gap:10px;">
                <span class="acpe-badge" style="margin-bottom:0;">{fa('user')} {ROLE_LABELS.get(user['role'], user['role'])}</span>
                <span style="font-weight:600;">{user['nom']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Déconnexion", key="logout_top_bar", type="secondary"):
            st.session_state.pop("user", None)
            st.rerun()
    st.markdown(f'<hr style="margin:4px 0 18px 0; border-color:{BORDER};">', unsafe_allow_html=True)


def chatbot_widget(bot_name, greeting, suggestions, answer_fn, state_key):
    """Widget de chat flottant (st.popover) réutilisable par les 3 profils.

    Utilise st.chat_message (composant natif Streamlit) plutôt que des <div> en HTML
    brut pour l'historique : un nombre de blocs HTML qui varie à chaque message entre
    deux rafraîchissements provoque une erreur frontend React ("NotFoundError:
    removeChild") propre à st.popover, que les composants natifs évitent."""
    history_key = f"chat_history_{state_key}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    with st.popover(f"💬 {bot_name}", use_container_width=False):
        st.markdown(f"**{bot_name}**")
        st.caption(greeting)
        for role, msg in st.session_state[history_key][-6:]:
            with st.chat_message("user" if role == "user" else "assistant"):
                st.markdown(msg)

        cols = st.columns(len(suggestions))
        for c, s in zip(cols, suggestions):
            if c.button(s, key=f"{state_key}_sugg_{s}", use_container_width=True):
                st.session_state[history_key].append(("user", s))
                st.session_state[history_key].append(("bot", answer_fn(s)))
                st.rerun()

        question = st.chat_input("Posez votre question...", key=f"{state_key}_input")
        if question:
            st.session_state[history_key].append(("user", question))
            st.session_state[history_key].append(("bot", answer_fn(question)))
            st.rerun()


@st.cache_data
def _load_congo_images():
    images = []
    if os.path.isdir(ASSETS_DIR):
        for fname in sorted(os.listdir(ASSETS_DIR)):
            ext = fname.lower().rsplit(".", 1)[-1] if "." in fname else ""
            if ext not in ("jpg", "jpeg", "png", "webp"):
                continue
            with open(os.path.join(ASSETS_DIR, fname), "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            mime = "jpeg" if ext == "jpg" else ext
            images.append(f"data:image/{mime};base64,{b64}")
    return images


def congo_background(interval_s=6):
    """Défilement (fondu enchaîné) de photos du Congo en arrière-plan de la page de
    connexion. Lit les images depuis application/images/congo/ (voir README dans ce dossier).
    En l'absence d'image, un dégradé aux couleurs du drapeau congolais est utilisé."""
    images = _load_congo_images()

    if not images:
        st.markdown(
            """
            <style>
            .congo-bg {
                position: fixed; inset: 0; z-index: -2; background-size: 400% 400%;
                background-image: linear-gradient(120deg, #009543, #FBDE4A, #DC241F);
                opacity: 0.10; animation: congoGradient 20s ease infinite;
            }
            .congo-overlay { position: fixed; inset: 0; z-index: -1; background: rgba(255,255,255,0.55); }
            @keyframes congoGradient {
                0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            </style>
            <div class="congo-bg"></div><div class="congo-overlay"></div>
            """,
            unsafe_allow_html=True,
        )
        return

    n = len(images)
    total = n * interval_s
    slot = 100 / n
    fade_in = slot * 0.15
    fade_out = slot * 0.85

    layers = "".join(
        f"""
        .congo-bg-{i} {{
            position: fixed; inset: 0; z-index: -2; background-image: url('{img}');
            background-size: cover; background-position: center; opacity: 0;
            animation: congoFade {total}s ease-in-out infinite;
            animation-delay: -{i * interval_s}s;
        }}
        """
        for i, img in enumerate(images)
    )
    divs = "".join(f'<div class="congo-bg-{i}"></div>' for i in range(n))

    st.markdown(
        f"""
        <style>
        {layers}
        @keyframes congoFade {{
            0% {{ opacity: 0; }}
            {fade_in:.2f}% {{ opacity: 1; }}
            {fade_out:.2f}% {{ opacity: 1; }}
            {slot:.2f}% {{ opacity: 0; }}
            100% {{ opacity: 0; }}
        }}
        .congo-overlay {{ position: fixed; inset: 0; z-index: -1; background: rgba(255,255,255,0.62); }}
        </style>
        {divs}
        <div class="congo-overlay"></div>
        """,
        unsafe_allow_html=True,
    )
