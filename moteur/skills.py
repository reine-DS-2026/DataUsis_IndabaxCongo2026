# -*- coding: utf-8 -*-
"""Bonus 2 : analyse des écarts de compétences (Skill Gap).

Extraction par référentiel de compétences (mots-clés) sur le champ Compétences /
Profil / Description des offres enrichies, comparée au texte disponible côté candidat.
Limitation assumée : ne couvre que les 143 offres disposant de texte libre riche.
"""
import re
import unicodedata

SKILL_REFERENTIAL = [
    "Docker", "Git", "Kubernetes", "Linux", "Windows", "Power BI", "Excel", "Word",
    "PowerPoint", "SQL", "Python", "Java", "JavaScript", "PHP", "C++", "R",
    "SAP", "Sage", "Photoshop", "AutoCAD", "SolidWorks", "Anglais", "Comptabilité",
    "Gestion de projet", "Management", "Leadership", "Communication", "Négociation",
    "Marketing digital", "SEO", "Réseaux sociaux", "Logistique", "HSE", "QHSE",
    "Maintenance industrielle", "Électricité", "Électromécanique", "Soudure",
    "Conduite d'engins", "Permis B", "Permis C", "Premiers secours", "CACES",
    "Analyse financière", "Audit", "Fiscalité", "Droit du travail", "Recrutement",
    "Formation", "Facturation", "Reporting", "Data Analysis", "Machine Learning",
    "Networking", "Cybersécurité", "Télécommunications", "Génie civil", "Topographie",
]


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize(s):
    return strip_accents(str(s)).lower().strip()


def _contains_skill(text, skill):
    text_n = normalize(text)
    skill_n = normalize(skill)
    return re.search(r"(?<!\w)" + re.escape(skill_n) + r"(?!\w)", text_n) is not None


def extract_offer_skills(offer_row):
    """Compétences citées dans l'offre (Compétences, Profil, Description)."""
    text = " ".join(filter(None, [
        offer_row.get("competences"), offer_row.get("profil"), offer_row.get("description"),
    ]))
    if not text.strip():
        return []
    return [s for s in SKILL_REFERENTIAL if _contains_skill(text, s)]


def candidate_known_skills(candidate_row):
    """Signal textuel disponible côté candidat pour vérifier la maîtrise d'une compétence.
    Inclut le texte du CV (text_rich) pour les profils créés par upload de CV."""
    text = " ".join(filter(None, [
        candidate_row.get("qualification_raw"), candidate_row.get("qualification_metier"),
        candidate_row.get("diplome"), candidate_row.get("filiere"), candidate_row.get("metier_vise"),
        candidate_row.get("text_rich"),
        " ".join(candidate_row.get("cv_competences") or []),
    ]))
    return text


def skill_gap(candidate_row, offer_row):
    """Retourne (compétences_acquises, compétences_manquantes) pour la paire donnée.
    Renvoie (None, None) si l'offre ne dispose pas de texte riche (94,4% du catalogue)."""
    if not offer_row.get("has_rich_text"):
        return None, None
    required = extract_offer_skills(offer_row)
    if not required:
        return [], []
    cand_text = candidate_known_skills(candidate_row)
    acquises = [s for s in required if _contains_skill(cand_text, s)]
    manquantes = [s for s in required if s not in acquises]
    return acquises, manquantes
