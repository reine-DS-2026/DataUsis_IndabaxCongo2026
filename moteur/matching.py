# -*- coding: utf-8 -*-
"""Moteur d'appariement hybride à 3 couches (cf. Rapport_Methodologique_ACPE_IndabaX2026.docx, section 3).

Couche 1 (secteur + localisation) : similarité textuelle légère entre secteur_metier du
    candidat et secteur_offre, combinée à un score de localisation dérivé du département
    (Matricule) et de la mobilité déclarée. Implémentée comme une contribution continue
    (pas un filtre booléen dur) pour éviter le risque de short-list vide identifié dans
    l'audit méthodologique -- le "filtrage en cascade" ne sert qu'à réduire l'espace de
    recherche avant scoring, jamais à exclure définitivement un candidat de tout résultat.
Couche 2 (texte) : TF-IDF + cosinus sur les intitulés/qualifications (100% du catalogue),
    enrichi par un second TF-IDF sur les champs Description/Profil/Compétences (5,6% du
    catalogue, cf. Offres_ACPE_Extensions).
Couche 3 (structure) : compatibilité contractuelle (Objectif candidat vs Groupe de contrat
    offre) -- les seules variables structurées disponibles côté offre pour 100% du catalogue.

Score final = w1 * secteur_localisation + w2 * texte + w3 * structure.
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_prep import NON_RENSEIGNE

# Calibrés par recherche d'hyperparamètres sur le jeu de validation (800 candidats,
# jamais le test), cf. donnees_generees/weight_calibration.json et moteur/calibrate_weights.py.
DEFAULT_WEIGHTS = {"secteur_localisation": 0.21, "texte": 0.70, "structure": 0.09}

# scikit-learn ne fournit pas de liste de mots vides français : sans ce filtre, des mots
# purement grammaticaux ("de", "le", "un"...) ressortent comme termes explicatifs à forte
# similarité simplement parce qu'ils sont fréquents des deux côtés (candidat et offre).
FRENCH_STOPWORDS = frozenset("""
    au aux avec ce ces dans de des du elle en et eux il je la le leur lui ma mais me
    même mes moi mon ne nos notre nous on ou où par pas pour qu que qui sa se ses son
    sur ta te tes toi ton tu un une vos votre vous c d j l à m n s t y été étée étées
    étés étant suis es est sommes êtes sont serai seras sera serons serez seront étais
    était étions étiez étaient fus fut fûmes fûtes furent sois soit soyons soyez soient
    fusse fusses fût fussions fussiez fussent ayant eu eue eues eus ai as avons avez ont
    aurai auras aura aurons aurez auront avais avait avions aviez avaient eut eûmes eûtes
    eurent aie aies ait ayons ayez aient eusse eusses eût eussions eussiez eussent ceci
    cela celà cet cette ici ils les leurs quel quels quelle quelles sans soi
""".split())


def _dedupe_ngrams(scored_terms):
    """Retire les termes redondants : si un unigramme est déjà couvert par un bigramme
    mieux classé (ex: "chef" alors que "chef de salle" est déjà retenu), il est ignoré."""
    kept = []
    for term, score in scored_terms:
        if any(term in bigger and term != bigger for bigger, _ in kept):
            continue
        kept = [(t, s) for t, s in kept if not (t in term and t != term)]
        kept.append((term, score))
    return kept

CONTRACT_COMPAT = {
    "Emploi": {"Emploi Temporaire": 1.0, "Emploi Durable": 1.0, "Stages Classiques": 0.2,
               "Alternance": 0.3, NON_RENSEIGNE: 0.6},
    "Stage": {"Emploi Temporaire": 0.3, "Emploi Durable": 0.1, "Stages Classiques": 1.0,
              "Alternance": 0.6, NON_RENSEIGNE: 0.5},
    "Formation": {"Emploi Temporaire": 0.2, "Emploi Durable": 0.1, "Stages Classiques": 0.5,
                  "Alternance": 1.0, NON_RENSEIGNE: 0.4},
}


def contract_score(objectif, groupe_contrat):
    return CONTRACT_COMPAT.get(objectif, {}).get(groupe_contrat, 0.4)


def location_score(candidate_departement, offer_departement, mobilite):
    if mobilite == "Oui":
        return 1.0
    if candidate_departement == offer_departement and candidate_departement != "Non déterminé":
        return 1.0
    if mobilite == "Non déclaré":
        return 0.5
    return 0.1  # mobilite == "Non" et département différent


class MatchingEngine:
    def __init__(self, offers, candidates, weights=None):
        self.offers = offers.reset_index(drop=True)
        self.candidates = candidates.set_index("candidate_id", drop=False)
        self.weights = weights or DEFAULT_WEIGHTS
        self._fit()

    def _fit(self):
        offers = self.offers
        candidates = self.candidates

        # --- Couche 2a : texte léger (100% du catalogue), vocabulaire partagé.
        light_corpus = pd.concat([offers["text_light"], candidates["text_light"]], ignore_index=True)
        self.light_vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2), max_features=20000, stop_words=list(FRENCH_STOPWORDS))
        self.light_vec.fit(light_corpus)
        self.offers_light = self.light_vec.transform(offers["text_light"])

        # --- Couche 2b : texte riche (5,6% du catalogue), boost.
        rich_docs = offers.loc[offers["has_rich_text"], "text_rich"]
        self.rich_vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2), max_features=20000, stop_words=list(FRENCH_STOPWORDS))
        if len(rich_docs) > 0:
            self.rich_vec.fit(rich_docs)
            self.offers_rich = self.rich_vec.transform(offers["text_rich"].fillna(""))
        else:
            self.offers_rich = None

        # --- Couche 1 : similarité sectorielle (secteur_metier candidat vs secteur_offre).
        sector_corpus = pd.concat([offers["secteur_offre"], candidates["secteur_metier"]], ignore_index=True)
        self.sector_vec = TfidfVectorizer(min_df=1, ngram_range=(1, 2), max_features=10000, stop_words=list(FRENCH_STOPWORDS))
        self.sector_vec.fit(sector_corpus)
        self.offers_sector = self.sector_vec.transform(offers["secteur_offre"])

        self._offer_departement = offers["departement_offre"].values
        self._offer_groupe_contrat = offers["groupe_contrat"].values

        # Matrices côté candidat, pré-calculées pour le sens inverse offre -> candidats
        # (profil Recruteur : Top-K candidats pour une offre donnée).
        self.candidates_light = self.light_vec.transform(candidates["text_light"])
        self.candidates_sector = self.sector_vec.transform(candidates["secteur_metier"])
        self.candidates_rich = (
            self.rich_vec.transform(candidates["text_rich"]) if self.offers_rich is not None else None
        )
        self._cand_departement = candidates["departement"].values
        self._cand_mobilite = candidates["mobilite"].values
        self._cand_objectif = candidates["objectif"].values
        self._cand_ids = candidates["candidate_id"].values

    def _candidate_vectors(self, cand_row):
        light_v = self.light_vec.transform([cand_row["text_light"]])
        sector_v = self.sector_vec.transform([cand_row["secteur_metier"]])
        rich_v = self.rich_vec.transform([cand_row["text_rich"]]) if self.offers_rich is not None else None
        return light_v, sector_v, rich_v

    def _shortlist_mask(self, cand_row, min_size=10):
        """Filtrage progressif : chaque critère n'est retenu que s'il laisse au moins
        min_size offres, sinon il est relâché (jamais de short-list vide)."""
        n = len(self.offers)
        mask = np.ones(n, dtype=bool)

        # 1. secteur : on ne garde que les offres à similarité sectorielle non nulle.
        sector_v = self.sector_vec.transform([cand_row["secteur_metier"]])
        sector_sim = cosine_similarity(sector_v, self.offers_sector).ravel()
        sector_mask = sector_sim > 0.05
        if sector_mask.sum() >= min_size:
            mask &= sector_mask

        # 2. localisation : si mobilite == "Non", restreindre strictement au département.
        if cand_row["mobilite"] == "Non":
            loc_mask = self._offer_departement == cand_row["departement"]
            if (mask & loc_mask).sum() >= min_size:
                mask &= loc_mask

        # 3. contrat : exclure les incompatibilités franches (score < 0.2).
        contract_mask = np.array([
            contract_score(cand_row["objectif"], gc) >= 0.2 for gc in self._offer_groupe_contrat
        ])
        if (mask & contract_mask).sum() >= min_size:
            mask &= contract_mask

        if mask.sum() < min_size:
            mask = np.ones(n, dtype=bool)  # filet de sécurité ultime
        return mask, sector_sim

    def recommend(self, candidate_id, k=10, min_shortlist=30):
        cand_row = self.candidates.loc[candidate_id]
        return self.recommend_for_profile(cand_row, k=k, min_shortlist=min_shortlist)

    def recommend_for_profile(self, cand_row, k=10, min_shortlist=30):
        """Identique à recommend(), mais accepte un profil candidat ad-hoc (dict ou Series)
        qui n'est pas nécessairement présent dans self.candidates -- utilisé pour les comptes
        Demandeur créés à partir d'un CV plutôt que d'un Matricule existant du dataset."""
        mask, sector_sim = self._shortlist_mask(cand_row, min_size=max(k, min_shortlist))
        idx = np.where(mask)[0]

        light_v, sector_v, rich_v = self._candidate_vectors(cand_row)
        light_sim = cosine_similarity(light_v, self.offers_light[idx]).ravel()
        text_score = light_sim.copy()
        if self.offers_rich is not None:
            rich_sim = cosine_similarity(rich_v, self.offers_rich[idx]).ravel()
            has_rich = self.offers.loc[idx, "has_rich_text"].values
            text_score = np.where(has_rich, 0.5 * light_sim + 0.5 * rich_sim, light_sim)

        loc_scores = np.array([
            location_score(cand_row["departement"], self._offer_departement[i], cand_row["mobilite"])
            for i in idx
        ])
        sector_localisation = 0.6 * sector_sim[idx] + 0.4 * loc_scores

        structure_score = np.array([
            contract_score(cand_row["objectif"], gc) for gc in self._offer_groupe_contrat[idx]
        ])

        w = self.weights
        final = (
            w["secteur_localisation"] * sector_localisation +
            w["texte"] * text_score +
            w["structure"] * structure_score
        )

        result = self.offers.loc[idx, [
            "offer_id", "intitule", "entreprise", "secteur_offre", "lieu",
            "type_contrat", "groupe_contrat", "has_rich_text",
        ]].copy()
        result["score_secteur_localisation"] = sector_localisation
        result["score_texte"] = text_score
        result["score_structure"] = structure_score
        result["score_final"] = final
        result = result.sort_values("score_final", ascending=False).head(k).reset_index(drop=True)
        result.insert(0, "rank", np.arange(1, len(result) + 1))
        return result

    def recommend_candidates(self, offer_row, k=10):
        """Sens inverse du moteur : Top-K candidats pour une offre donnée (profil Recruteur).
        offer_row peut être une ligne existante de self.offers ou un dict/Series ad-hoc
        (offre en cours de saisie dans la console de publication guidée)."""
        text_light = offer_row.get("text_light") or offer_row.get("intitule", "")
        light_v = self.light_vec.transform([text_light])
        text_sim = cosine_similarity(light_v, self.candidates_light).ravel()

        has_rich = bool(offer_row.get("has_rich_text")) and self.candidates_rich is not None
        if has_rich:
            rich_v = self.rich_vec.transform([offer_row.get("text_rich", "")])
            rich_sim = cosine_similarity(rich_v, self.candidates_rich).ravel()
            text_score = 0.5 * text_sim + 0.5 * rich_sim
        else:
            text_score = text_sim

        sector_v = self.sector_vec.transform([offer_row.get("secteur_offre", "")])
        sector_sim = cosine_similarity(sector_v, self.candidates_sector).ravel()

        offer_departement = offer_row.get("departement_offre", "Non déterminé")
        offer_groupe_contrat = offer_row.get("groupe_contrat", NON_RENSEIGNE)

        loc_scores = np.array([
            location_score(dep, offer_departement, mob)
            for dep, mob in zip(self._cand_departement, self._cand_mobilite)
        ])
        sector_localisation = 0.6 * sector_sim + 0.4 * loc_scores

        structure_score = np.array([
            contract_score(obj, offer_groupe_contrat) for obj in self._cand_objectif
        ])

        w = self.weights
        final = (
            w["secteur_localisation"] * sector_localisation +
            w["texte"] * text_score +
            w["structure"] * structure_score
        )

        result = self.candidates.reset_index(drop=True)[[
            "candidate_id", "qualification_metier", "secteur_metier", "metier_vise",
            "departement", "niveau_etude", "objectif",
        ]].copy()
        result["score_secteur_localisation"] = sector_localisation
        result["score_texte"] = text_score
        result["score_structure"] = structure_score
        result["score_final"] = final
        result = result.sort_values("score_final", ascending=False).head(k).reset_index(drop=True)
        result.insert(0, "rank", np.arange(1, len(result) + 1))
        return result

    def score_pair(self, cand_row, offer_row):
        """Score une paire candidat/offre unique -- utilisé par le simulateur "what-if"
        (impact d'une compétence ou d'un changement de mobilité sur la compatibilité),
        avec un candidat réel ou hypothétique (dict/Series modifiée en mémoire)."""
        light_v = self.light_vec.transform([cand_row["text_light"]])
        offer_light_v = self.offers_light[self.offers.index[self.offers["offer_id"] == offer_row["offer_id"]][0]]
        text_sim = cosine_similarity(light_v, offer_light_v).toarray()[0, 0]

        if offer_row.get("has_rich_text") and self.offers_rich is not None:
            rich_v = self.rich_vec.transform([cand_row.get("text_rich", "")])
            offer_pos = self.offers.index[self.offers["offer_id"] == offer_row["offer_id"]][0]
            rich_sim = cosine_similarity(rich_v, self.offers_rich[offer_pos]).toarray()[0, 0]
            text_score = 0.5 * text_sim + 0.5 * rich_sim
        else:
            text_score = text_sim

        sector_v = self.sector_vec.transform([cand_row["secteur_metier"]])
        offer_sector_v = self.offers_sector[self.offers.index[self.offers["offer_id"] == offer_row["offer_id"]][0]]
        sector_sim = cosine_similarity(sector_v, offer_sector_v).toarray()[0, 0]

        loc = location_score(cand_row["departement"], offer_row["departement_offre"], cand_row["mobilite"])
        sector_localisation = 0.6 * sector_sim + 0.4 * loc
        structure = contract_score(cand_row["objectif"], offer_row["groupe_contrat"])

        w = self.weights
        final = (
            w["secteur_localisation"] * sector_localisation +
            w["texte"] * text_score +
            w["structure"] * structure
        )
        return {
            "score_secteur_localisation": float(sector_localisation),
            "score_texte": float(text_score),
            "score_structure": float(structure),
            "score_final": float(final),
        }

    def explain_terms(self, candidate_id, offer_id, top_n=5):
        """Termes ayant le plus contribué à la similarité textuelle légère (explicabilité)."""
        cand_row = self.candidates.loc[candidate_id]
        return self.explain_terms_for_profile(cand_row, offer_id, top_n=top_n)

    def explain_terms_for_profile(self, cand_row, offer_id, top_n=5):
        offer_pos = self.offers.index[self.offers["offer_id"] == offer_id][0]
        light_v = self.light_vec.transform([cand_row["text_light"]]).toarray().ravel()
        offer_v = self.offers_light[offer_pos].toarray().ravel()
        product = light_v * offer_v
        if product.sum() == 0:
            return []
        # Marge plus large que top_n car _dedupe_ngrams réduit ensuite la liste
        # (un unigramme couvert par un bigramme mieux classé est éliminé).
        top_idx = np.argsort(product)[::-1][: top_n * 4]
        vocab = np.array(self.light_vec.get_feature_names_out())
        candidates = [(vocab[i], float(product[i])) for i in top_idx if product[i] > 0]
        return _dedupe_ngrams(candidates)[:top_n]
