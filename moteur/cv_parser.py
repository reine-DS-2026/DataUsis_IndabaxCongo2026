# -*- coding: utf-8 -*-
"""Extraction de texte et de compétences à partir d'un CV téléversé (PDF/DOCX/TXT),
pour les comptes Demandeur créés sans Matricule ACPE existant.

Limitation assumée : l'extraction de compétences repose sur le même référentiel par
mots-clés que le Skill Gap (skills.py), pas sur un NER entraîné -- suffisant pour un
prototype de hackathon, mais ne couvre que les compétences déjà listées dans le référentiel.
"""
import io

from skills import SKILL_REFERENTIAL, _contains_skill


def extract_text(uploaded_file):
    """uploaded_file : objet retourné par st.file_uploader (a .name et lecture bytes)."""
    name = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith(".pdf"):
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if name.endswith(".docx"):
        import docx
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)

    # .txt ou format non reconnu : tentative de décodage brut.
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_skills_from_text(cv_text):
    if not cv_text or not cv_text.strip():
        return []
    return [s for s in SKILL_REFERENTIAL if _contains_skill(cv_text, s)]


def build_profile_from_cv(cv_text, structured):
    """Construit un profil candidat ad-hoc combinant le texte du CV (utilisé par la
    couche 2 du moteur, TF-IDF) et les champs structurés saisis dans le formulaire
    (utilisés par les couches 1 et 3)."""
    competences = extract_skills_from_text(cv_text)
    cv_excerpt = " ".join(cv_text.split())[:6000]

    text_light = " ".join(filter(None, [
        structured.get("metier_vise"), structured.get("secteur_metier"), cv_excerpt[:1000],
    ])).strip()
    text_rich = " ".join(filter(None, [text_light, cv_excerpt])).strip()

    profile = dict(structured)
    profile.update({
        "candidate_id": None,
        "text_light": text_light,
        "text_rich": text_rich,
        "cv_competences": competences,
        "qualification_metier": structured.get("metier_vise", ""),
        "qualification_raw": structured.get("metier_vise", ""),
        "filiere": structured.get("secteur_metier", ""),
    })
    return profile, competences
