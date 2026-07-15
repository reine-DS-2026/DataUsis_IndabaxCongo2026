# -*- coding: utf-8 -*-
"""Chargement et nettoyage des 4 jeux de données ACPE.

Anomalies gérées ici (cf. Rapport_Methodologique_ACPE_IndabaX2026.docx, section 2) :
- Matricule dupliqué (13 cas, 26 lignes) -> candidate_id composite basé sur la position de ligne.
- id_demandeur non unique dans Appariement -> même composite, construit par alignement de ligne
  (Demandeurs.xlsx et Appariement_Demandeurs_Offres.xlsx sont parfaitement alignés ligne à ligne).
- Référence offre dupliquée (JOB250002109, 5 lignes) -> désambiguïsée nativement par la colonne
  Poste, qui forme avec Référence une clé composite unique sur les 2535 lignes.
- Offres_ACPE_Extensions : les 143 références sont exactement les 143 lignes à Poste vide du
  fichier principal -> jointure left join sur la référence, jamais de concaténation.
- Secteur d'activité manquant (9,6%) -> catégorie explicite "Non renseigné".
- Mobilité géographique à 90,6% "Non déclaré" -> le département déduit du préfixe du Matricule
  sert de repli géographique (cf. section 2.1 du rapport méthodologique).
"""
import os
import re
import unicodedata

import pandas as pd
import openpyxl

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DONNEES_GENEREES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "donnees_generees")

DEMANDEURS_FILE = "Demandeurs .xlsx"
OFFRES_FILE = "Offres_ACPE.xlsx"
EXTENSIONS_FILE = "Offres_ACPE_Extensions.xlsx"
APPARIEMENT_FILE = "Appariement_Demandeurs_Offres.xlsx"

NON_RENSEIGNE = "Non renseigné"

# Préfixe de Matricule -> département d'origine (cf. découverte section 2.1 du rapport).
DEPARTEMENT_FROM_PREFIX = {
    "PPBZV": "Brazzaville",
    "PPPNR": "Pointe-Noire",
    "PPBOU": "Bouenza",
    "PPLIK": "Likouala",
    "PPPLA": "Plateaux",
    "PPNIA": "Niari",
    "PPPOO": "Pool",
    "PPLEK": "Lékoumou",
    "PPKOU": "Kouilou",
    "PPSAN": "Sangha",
    "PPCUV": "Cuvette",
    "PPCVO": "Cuvette-Ouest",
    "PPPARIS": "Diaspora (Paris)",
    "PPAUT": "Autre",
    "PPAUTRE": "Autre",
}

# Ville/localité d'offre -> département (référentiel Congo-Brazzaville, best-effort).
VILLE_TO_DEPARTEMENT = {
    "BRAZZAVILLE": "Brazzaville",
    "POINTE-NOIRE": "Pointe-Noire",
    "POINTE NOIRE": "Pointe-Noire",
    "NKAYI": "Bouenza",
    "MADINGOU": "Bouenza",
    "BOUANSA": "Bouenza",
    "BOUENZA": "Bouenza",
    "MOUYONDZI": "Bouenza",
    "KOUILOU": "Kouilou",
    "HINDA": "Kouilou",
    "KAYES": "Kouilou",
    "MADINGO-KAYES": "Kouilou",
    "DOLISIE": "Niari",
    "NIARI": "Niari",
    "MOSSENDJO": "Niari",
    "MAYOKO": "Niari",
    "DIVENIE": "Niari",
    "SIBITI": "Lékoumou",
    "LEKOUMOU": "Lékoumou",
    "ZANAGA": "Lékoumou",
    "IMPFONDO": "Likouala",
    "LIKOUALA": "Likouala",
    "DONGOU": "Likouala",
    "EPENA": "Likouala",
    "OUESSO": "Sangha",
    "SANGHA": "Sangha",
    "PIKOUNDA": "Sangha",
    "OWANDO": "Cuvette",
    "OYO": "Cuvette",
    "CUVETTE": "Cuvette",
    "BOUNDJI": "Cuvette",
    "EWO": "Cuvette-Ouest",
    "KELLE": "Cuvette-Ouest",
    "DJAMBALA": "Plateaux",
    "GAMBOMA": "Plateaux",
    "LEKANA": "Plateaux",
    "PLATEAUX": "Plateaux",
    "KINKALA": "Pool",
    "MINDOULI": "Pool",
    "KINDAMBA": "Pool",
    "POOL": "Pool",
}


def strip_accents(s):
    if not isinstance(s, str):
        return s
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_upper(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    return strip_accents(s).upper()


def clean_str(s):
    if s is None:
        return None
    s = str(s).strip()
    return s if s != "" else None


def get(row, i):
    return row[i] if i < len(row) else None


def _read_sheet(fname, sheet):
    path = os.path.join(DATA_DIR, fname)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else h for h in rows[0]]
    return header, rows[1:]


def matricule_prefix(matricule):
    m = re.match(r"^([A-Z]+)\d", matricule)
    return m.group(1) if m else None


def load_offers():
    header, rows = _read_sheet(OFFRES_FILE, "Feuil1")
    idx = {h: i for i, h in enumerate(header)}

    records = []
    for r in rows:
        ref = r[idx["Référence offre"]]
        poste = r[idx["Poste"]]
        offer_id = ref if poste in (None, 1.0) else f"{ref}_P{int(poste)}"
        # JOB250002109 a 5 lignes -> Poste 1..5 distingue déjà, mais seule Poste=1 doit
        # rester "JOB250002109" nu pour rester cohérente avec Appariement (qui référence
        # la clé nue) ; les 4 autres deviennent JOB250002109_P2..P5.
        records.append({
            "offer_id": offer_id,
            "offer_ref": ref,
            "poste_num": poste,
            "intitule": clean_str(r[idx["Intitule"]]),
            "secteur_offre": clean_str(r[idx["Secteur activité"]]) or NON_RENSEIGNE,
            "entreprise": clean_str(r[idx["Entreprise"]]),
            "type_entreprise": clean_str(r[idx["Type d'entreprise"]]) or NON_RENSEIGNE,
            "lieu": clean_str(r[idx["Lieu"]]) or NON_RENSEIGNE,
            "groupe_contrat": clean_str(r[idx["Groupe de contrat"]]) or NON_RENSEIGNE,
            "type_contrat": clean_str(r[idx["Type contrat"]]) or NON_RENSEIGNE,
            "date_publication": r[idx["Date de publication"]],
            "description": None,
            "profil": None,
            "competences": None,
        })
    offers = pd.DataFrame.from_records(records)
    offers["departement_offre"] = offers["lieu"].apply(
        lambda v: VILLE_TO_DEPARTEMENT.get(norm_upper(v), v)
    )
    offers["date_publication"] = pd.to_datetime(offers["date_publication"], errors="coerce")

    # Jointure Extensions (left join sur la référence nue, jamais de concaténation).
    ext_header, ext_rows = _read_sheet(EXTENSIONS_FILE, "Offres Avril 2026")
    ext_idx = {h: i for i, h in enumerate(ext_header)}
    ext_map = {}
    for r in ext_rows:
        ref = get(r, ext_idx["Référence"])
        if ref is None:
            continue
        ext_map[ref] = {
            "description": clean_str(get(r, ext_idx["Description"])),
            "profil": clean_str(get(r, ext_idx["Profil"])),
            "competences": clean_str(get(r, ext_idx["Compétences"])),
        }

    for col in ["description", "profil", "competences"]:
        offers[col] = offers["offer_ref"].map(lambda ref: ext_map.get(ref, {}).get(col))

    offers["has_rich_text"] = offers["description"].notna()

    offers["text_light"] = offers["intitule"].fillna("")
    offers["text_rich"] = (
        offers["description"].fillna("") + " " +
        offers["profil"].fillna("") + " " +
        offers["competences"].fillna("")
    ).str.strip()

    return offers.reset_index(drop=True)


def load_candidates():
    header, rows = _read_sheet(DEMANDEURS_FILE, "Feuil1")
    idx = {h: i for i, h in enumerate(header)}

    # clé composite par position de ligne (row-aligned avec Appariement).
    matricule_counts = {}
    records = []
    for row_pos, r in enumerate(rows):
        matricule = r[idx["Matricule"]]
        matricule_counts[matricule] = matricule_counts.get(matricule, 0) + 1
        occurrence = matricule_counts[matricule]
        candidate_id = matricule if occurrence == 1 else f"{matricule}_{occurrence}"

        mobilite = clean_str(r[idx["Mobilité géographique"]]) or "Non déclaré"
        prefix = matricule_prefix(matricule)
        departement = DEPARTEMENT_FROM_PREFIX.get(prefix, "Non déterminé")

        records.append({
            "candidate_id": candidate_id,
            "matricule": matricule,
            "row_pos": row_pos,
            "age": r[idx["Age"]],
            "qualification_raw": clean_str(r[idx["Qualification"]]),
            "secteur_activite": clean_str(r[idx["Secteur d'activité"]]) or NON_RENSEIGNE,
            "objectif": clean_str(r[idx["Objectif"]]),
            "diplome": clean_str(r[idx["Diplome"]]),
            "genre": clean_str(r[idx["Genre"]]),
            "niveau_etude": clean_str(r[idx["niveau_etude"]]),
            "qualification_metier": clean_str(r[idx["qualification_metier"]]),
            "secteur_metier": clean_str(r[idx["secteur_metier"]]) or NON_RENSEIGNE,
            "filiere": clean_str(r[idx["Filière / Spécialité"]]),
            "secteur_demande": clean_str(r[idx["Secteur demandé"]]) or "Non déclaré",
            "metier_vise": clean_str(r[idx["Métier visé / Qualification visée"]]),
            "mobilite": mobilite,
            "departement": departement,
        })
    candidates = pd.DataFrame.from_records(records)

    candidates["text_light"] = (
        candidates["qualification_metier"].fillna("") + " " +
        candidates["metier_vise"].fillna("") + " " +
        candidates["filiere"].fillna("")
    ).str.strip()

    candidates["text_rich"] = (
        candidates["text_light"] + " " +
        candidates["diplome"].fillna("") + " " +
        candidates["niveau_etude"].fillna("")
    ).str.strip()

    return candidates.reset_index(drop=True)


def _canonical_offer_id_map(offers):
    """Retrouve l'offer_id composite (avec suffixe _P#) à partir de la référence nue,
    pour les lignes de vérité terrain qui ne référencent que Référence offre."""
    ref_to_ids = {}
    for _, row in offers.iterrows():
        ref_to_ids.setdefault(row["offer_ref"], []).append(row["offer_id"])
    return ref_to_ids


def load_ground_truth(offers):
    header, rows = _read_sheet(APPARIEMENT_FILE, "Sheet1")
    idx = {h: i for i, h in enumerate(header)}
    ref_to_ids = _canonical_offer_id_map(offers)

    matricule_counts = {}
    records = []
    for row_pos, r in enumerate(rows):
        matricule = r[idx["id_demandeur"]]
        matricule_counts[matricule] = matricule_counts.get(matricule, 0) + 1
        occurrence = matricule_counts[matricule]
        candidate_id = matricule if occurrence == 1 else f"{matricule}_{occurrence}"

        for rank, col in enumerate(["id_offre1", "id_offre2", "id_offre3"], start=1):
            ref = r[idx[col]]
            if ref is None:
                continue
            # Référence corrompue (JOB250002109) : ambiguë entre 5 postes, on la garde
            # telle quelle en pointant sur la 1ère variante (Poste=1 / MAGASINIER) plutôt
            # que de l'exclure, pour ne pas réduire la couverture du ground truth.
            candidate_offer_ids = ref_to_ids.get(ref, [ref])
            records.append({
                "candidate_id": candidate_id,
                "offer_id": candidate_offer_ids[0],
                "rank": rank,
            })
    return pd.DataFrame.from_records(records)


def build_all(cache=True):
    os.makedirs(DONNEES_GENEREES_DIR, exist_ok=True)
    cand_path = os.path.join(DONNEES_GENEREES_DIR, "candidates.parquet")
    off_path = os.path.join(DONNEES_GENEREES_DIR, "offers.parquet")
    gt_path = os.path.join(DONNEES_GENEREES_DIR, "ground_truth.parquet")

    if cache and all(os.path.exists(p) for p in (cand_path, off_path, gt_path)):
        candidates = pd.read_parquet(cand_path)
        offers = pd.read_parquet(off_path)
        ground_truth = pd.read_parquet(gt_path)
        return candidates, offers, ground_truth

    offers = load_offers()
    candidates = load_candidates()
    ground_truth = load_ground_truth(offers)

    offers.to_parquet(off_path, index=False)
    candidates.to_parquet(cand_path, index=False)
    ground_truth.to_parquet(gt_path, index=False)
    return candidates, offers, ground_truth


if __name__ == "__main__":
    c, o, g = build_all(cache=False)
    print("candidates:", c.shape)
    print("offers:", o.shape)
    print("ground_truth:", g.shape)
    print(c.head(3).T)
    print(o.head(3).T)
    print(g.head(6))
