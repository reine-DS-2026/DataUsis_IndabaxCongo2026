# -*- coding: utf-8 -*-
"""Authentification réelle (inspirée de l'architecture auth.py de l'équipe AirEka/DeepStats) :
base SQLite locale, mots de passe hachés (SHA-256 + sel aléatoire par utilisateur -- une
amélioration par rapport au SHA-256 nu, qui reste vulnérable aux rainbow tables sans sel).

Un compte Demandeur est créé soit à partir d'un Matricule ACPE existant (candidat déjà présent
dans le dataset), soit -- désormais le cas par défaut -- à partir d'un CV téléversé : le profil
dérivé (texte du CV, compétences détectées, champs structurés saisis) est alors stocké en JSON
dans la colonne profil_cv_json, puisqu'il ne correspond à aucune ligne du dataset d'origine.

Limitation assumée : ceci est un prototype de hackathon, pas un système d'authentification
de production (pas de politique de mot de passe, pas de limitation de tentatives, pas de
rotation de sel). Pour un déploiement réel, préférer bcrypt/argon2 et un vrai fournisseur
d'identité (SSO ACPE, cf. section "Espace Connexion Sécurisé - Conseiller ACPE" de
l'architecture applicative).
"""
import os
import sqlite3
import hashlib
import secrets
import datetime
import json

DONNEES_GENEREES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "donnees_generees")
DB_PATH = os.path.join(DONNEES_GENEREES_DIR, "users.db")

ROLES = ("demandeur", "recruteur", "conseiller")
CONSEILLER_ACCESS_CODE = "ACPE-CONSEILLER-2026"


def get_conn():
    os.makedirs(DONNEES_GENEREES_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL,
            candidate_id TEXT,
            entreprise TEXT,
            profil_cv_json TEXT,
            date_creation TEXT NOT NULL,
            derniere_connexion TEXT
        )
    """)
    # Migration idempotente pour les bases créées avant l'ajout du profil CV.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "profil_cv_json" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN profil_cv_json TEXT")
    conn.commit()
    conn.close()


def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return digest, salt


class AuthError(Exception):
    pass


def create_user(nom, email, password, role, candidate_id=None, entreprise=None, profil_cv=None):
    if role not in ROLES:
        raise AuthError(f"Rôle invalide : {role}")
    if not nom or not email or not password:
        raise AuthError("Nom, email et mot de passe sont obligatoires.")
    if len(password) < 6:
        raise AuthError("Le mot de passe doit contenir au moins 6 caractères.")
    if role == "demandeur" and not candidate_id and not profil_cv:
        raise AuthError("Un CV (ou, à défaut, un Matricule ACPE) est requis pour un compte Demandeur.")
    if role == "recruteur" and not entreprise:
        raise AuthError("Le nom de l'entreprise est requis pour un compte Recruteur.")

    init_db()
    conn = get_conn()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise AuthError("Un compte existe déjà avec cet email.")

    password_hash, salt = _hash_password(password)
    profil_cv_json = json.dumps(profil_cv, ensure_ascii=False) if profil_cv else None
    conn.execute(
        "INSERT INTO users (nom, email, password_hash, salt, role, candidate_id, entreprise, "
        "profil_cv_json, date_creation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (nom, email, password_hash, salt, role, candidate_id, entreprise, profil_cv_json,
         datetime.datetime.now().isoformat()),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    conn.close()
    return get_user_by_id(user_id)


def authenticate(email, password):
    init_db()
    conn = get_conn()
    row = conn.execute(
        "SELECT id, nom, email, password_hash, salt, role, candidate_id, entreprise, profil_cv_json "
        "FROM users WHERE email = ?", (email,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    user_id, nom, email_db, password_hash, salt, role, candidate_id, entreprise, profil_cv_json = row
    digest, _ = _hash_password(password, salt=salt)
    if digest != password_hash:
        conn.close()
        return None
    conn.execute("UPDATE users SET derniere_connexion = ? WHERE id = ?",
                 (datetime.datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    return {
        "id": user_id, "nom": nom, "email": email_db, "role": role,
        "candidate_id": candidate_id, "entreprise": entreprise,
        "profil_cv": json.loads(profil_cv_json) if profil_cv_json else None,
    }


def get_user_by_id(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, nom, email, role, candidate_id, entreprise, profil_cv_json FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "nom": row[1], "email": row[2], "role": row[3],
            "candidate_id": row[4], "entreprise": row[5],
            "profil_cv": json.loads(row[6]) if row[6] else None}


def count_users():
    init_db()
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n
