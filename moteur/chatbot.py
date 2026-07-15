# -*- coding: utf-8 -*-
"""Chatbot IA contextuel — moteur local sans clé API (par choix : garantit un fonctionnement
hors-ligne, sans coût ni dépendance réseau pendant la démonstration devant le jury).

Fonctionne par injection de contexte (profil, scores, KPIs) dans des réponses gabarits
sélectionnées par détection d'intention sur mots-clés (normalisés, insensibles aux accents).
Les gabarits sont rédigés comme des phrases complètes et personnalisées (prénom de
l'utilisateur, formulation variable selon le sous-score dominant) plutôt que comme un
simple compte-rendu de chiffres, pour rester agréables à lire dans une conversation.
"""
import unicodedata


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def _matches(q, *keywords):
    return any(k in q for k in keywords)


def _first_name(nom):
    if not nom:
        return ""
    return str(nom).strip().split(" ")[0]


SUGGESTIONS_DEMANDEUR = [
    "Pourquoi cette offre m'est-elle recommandée ?",
    "Quelles compétences me manquent ?",
    "Quelles sont mes meilleures offres ?",
]

SUGGESTIONS_RECRUTEUR = [
    "Pourquoi ce candidat correspond à mon offre ?",
    "Quel est le meilleur candidat ?",
]

SUGGESTIONS_CONSEILLER = [
    "Quels sont les secteurs qui recrutent le plus ?",
    "Où sont les zones de tension ?",
]


def _dominant_reason(rec_row):
    """Phrase naturelle expliquant la recommandation, centrée sur le sous-score qui
    contribue le plus, plutôt que d'énumérer les trois pourcentages bruts."""
    scores = {
        "texte": rec_row["score_texte"],
        "secteur_localisation": rec_row["score_secteur_localisation"],
        "structure": rec_row["score_structure"],
    }
    dominant = max(scores, key=scores.get)
    if dominant == "texte":
        return "surtout parce que vos qualifications correspondent de près au profil recherché"
    if dominant == "secteur_localisation":
        return "surtout parce que le secteur et la localisation de l'offre correspondent bien à votre profil"
    return "surtout parce que le type de contrat proposé correspond à ce que vous recherchez"


def answer_demandeur(question, cand_row, recs_df, engine, skill_gap_fn, offers_df, user_name=None):
    q = _norm(question)
    top = recs_df.iloc[0]
    prenom = _first_name(user_name)
    hail = f"{prenom}, " if prenom else ""

    if _matches(q, "pourquoi", "raison", "explique", "explication"):
        terms = engine.explain_terms_for_profile(cand_row, top["offer_id"])
        terms_str = ", ".join(t for t, _ in terms) if terms else "vos qualifications déclarées"
        pct = round(top["score_final"] * 100)
        return (
            f"{hail}l'offre qui vous correspond le mieux en ce moment est **{top['intitule']}** "
            f"chez {top['entreprise']}, avec un taux de compatibilité d'environ {pct} %. "
            f"C'est {_dominant_reason(top)}, notamment sur des points comme {terms_str}. "
            f"Le contrat proposé ({top['type_contrat']}) est également cohérent avec votre objectif."
        )

    if _matches(q, "competence", "manque", "gap", "ecart", "skill"):
        offer_row = offers_df.loc[offers_df["offer_id"] == top["offer_id"]].iloc[0]
        acquises, manquantes = skill_gap_fn(cand_row, offer_row)
        if acquises is None:
            return (
                f"{hail}pour l'offre la mieux classée ({top['intitule']}), je n'ai malheureusement pas "
                "assez de texte détaillé pour analyser les compétences requises : cette analyse n'est "
                "possible que pour les offres qui ont une description complète, soit environ 1 offre sur 18."
            )
        if not manquantes:
            return (
                f"Bonne nouvelle {prenom or ''} : vous semblez déjà réunir les compétences attendues "
                f"pour **{top['intitule']}**, aucun écart notable n'a été détecté."
            ).replace("  ", " ")
        return (
            f"Pour **{top['intitule']}**, il vous manquerait encore : {', '.join(manquantes)}. "
            f"En revanche, vous maîtrisez déjà "
            f"{', '.join(acquises) if acquises else 'les bases attendues pour ce poste'}. "
            "Développer ces compétences manquantes augmenterait sensiblement vos chances sur ce type d'offre."
        )

    if _matches(q, "combien", "meilleur", "top", "recommand", "classement"):
        lines = [f"{r['rank']}. {r['intitule']} chez {r['entreprise']} — environ {round(r['score_final']*100)} %"
                 for _, r in recs_df.head(3).iterrows()]
        return (
            f"Voici vos meilleures pistes actuellement :\n\n" + "\n".join(lines)
        )

    if _matches(q, "secteur", "departement", "lieu", "localisation", "ville"):
        return (
            f"Vous êtes actuellement positionné·e sur le secteur **{cand_row['secteur_metier']}**, "
            f"rattaché·e au département **{cand_row['departement']}**, avec une mobilité géographique "
            f"déclarée « {cand_row['mobilite']} »."
        )

    return (
        f"Je peux vous expliquer pourquoi une offre vous est recommandée, détailler les compétences qui "
        f"vous manqueraient, ou lister vos meilleures pistes du moment. Vous pouvez me demander par "
        f"exemple : « {SUGGESTIONS_DEMANDEUR[0]} »"
    )


def answer_recruteur(question, offer_row, recs_df, engine):
    q = _norm(question)
    top = recs_df.iloc[0]

    if _matches(q, "pourquoi", "raison", "explique"):
        terms = engine.explain_terms(top["candidate_id"], offer_row["offer_id"]) \
            if "offer_id" in offer_row else []
        terms_str = ", ".join(t for t, _ in terms) if terms else "les qualifications déclarées du candidat"
        pct = round(top["score_final"] * 100)
        return (
            f"Le profil qui ressort le mieux pour ce poste est le candidat **{top['candidate_id']}**, "
            f"avec un taux de compatibilité d'environ {pct} %. Cela s'explique {_dominant_reason(top)}, "
            f"en particulier sur {terms_str}."
        )

    if _matches(q, "meilleur", "top", "classement"):
        lines = [f"{r['rank']}. {r['candidate_id']} ({r['qualification_metier']}) — environ "
                 f"{round(r['score_final']*100)} %" for _, r in recs_df.head(3).iterrows()]
        return "Voici les profils les plus adaptés à cette offre en ce moment :\n\n" + "\n".join(lines)

    return (
        "Je peux vous expliquer pourquoi un candidat correspond à votre offre, ou vous indiquer les "
        f"meilleurs profils disponibles. Essayez par exemple : « {SUGGESTIONS_RECRUTEUR[0]} »"
    )


def answer_conseiller(question, stats, user_name=None):
    q = _norm(question)
    prenom = _first_name(user_name)
    hail = f"{prenom}, " if prenom else ""

    if _matches(q, "secteur", "recrute", "represente"):
        top_secteurs = list(stats["secteurs_offres_top10"].items())[:3]
        lines = ", ".join(f"{s} ({n} offres)" for s, n in top_secteurs)
        return f"{hail}les secteurs qui recrutent le plus actuellement sont : {lines}."

    if _matches(q, "tension", "zone", "departement", "geographie", "region"):
        dep_cand = stats["repartition_candidats_par_departement"]
        dep_off = stats["repartition_offres_par_departement"]
        ratios = {d: (dep_off.get(d, 0) / n * 100 if n else None) for d, n in dep_cand.items()}
        ratios = {d: r for d, r in ratios.items() if r is not None}
        tension = sorted(ratios.items(), key=lambda x: x[1])[:3]
        lines = ", ".join(f"{d} ({r:.1f} offres pour 100 candidats)" for d, r in tension)
        return (
            f"Les départements où l'offre est la plus rare par rapport au nombre de candidats sont : "
            f"{lines}. Ce sont les zones à surveiller en priorité."
        )

    if _matches(q, "compatibilite", "taux", "moyen"):
        return (
            f"En moyenne, le meilleur candidat de chaque offre affiche un taux de compatibilité "
            f"d'environ {stats['taux_moyen_compatibilite_top1']*100:.0f} %."
        )

    return (
        f"{hail}je peux résumer les secteurs qui recrutent le plus ou identifier les zones de tension "
        f"géographique. Essayez par exemple : « {SUGGESTIONS_CONSEILLER[0]} »"
    )
