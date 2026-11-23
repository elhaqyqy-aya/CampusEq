"""Configuration du laboratoire : connexion PostgreSQL et chemins de sortie.

Aucun mot de passe n'est écrit dans les fichiers remis. La connexion vient de
l'environnement :

    DATABASE_URL=postgresql://campusequip@127.0.0.1:5432/campusequip

ou, si DATABASE_URL est absente, des variables standard libpq (PGHOST, PGPORT,
PGDATABASE, PGUSER, PGPASSWORD). Un fichier `.env` à la racine du projet est lu
s'il existe — il sert au poste de travail et n'est jamais remis (voir
`.gitignore` et `.env.exemple`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

URL_PAR_DEFAUT = 'postgresql://campusequip@127.0.0.1:5432/campusequip'


def charger_env(fichier: Path | None = None) -> None:
    """Charge un fichier KEY=VALUE sans écraser l'environnement existant."""
    fichier = fichier or RACINE / '.env'
    if not fichier.is_file():
        return
    for ligne in fichier.read_text(encoding='utf-8').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#') or '=' not in ligne:
            continue
        cle, valeur = ligne.split('=', 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def url_base() -> str:
    charger_env()
    return os.environ.get('DATABASE_URL', URL_PAR_DEFAUT)


def parametres_connexion() -> dict:
    """Paramètres acceptés par psycopg2.connect.

    Une DATABASE_URL est transmise telle quelle (psycopg2 sait la lire) ; sinon
    on laisse libpq utiliser ses variables d'environnement.
    """
    url = url_base()
    parametres = {'dsn': url, 'application_name': 'campusequip'}
    if os.environ.get('CAMPUSEQUIP_CONNECT_TIMEOUT'):
        parametres['connect_timeout'] = int(os.environ['CAMPUSEQUIP_CONNECT_TIMEOUT'])
    return parametres


def dossier_rapports() -> Path:
    chemin = Path(os.environ.get('CAMPUSEQUIP_RAPPORTS', RACINE / 'rapports'))
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def dossier_quarantaine() -> Path:
    chemin = Path(os.environ.get('CAMPUSEQUIP_QUARANTAINE', RACINE / 'quarantaine'))
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


@dataclass(frozen=True)
class Sorties:
    rapports: Path
    quarantaine: Path

    @classmethod
    def par_defaut(cls) -> 'Sorties':
        return cls(dossier_rapports(), dossier_quarantaine())


def nom_base(url: str | None = None) -> str:
    """Nom de la base, pour l'afficher sans jamais montrer de mot de passe."""
    url = url or url_base()
    sans_parametres = url.split('?', 1)[0]
    return sans_parametres.rsplit('/', 1)[-1] or '(inconnue)'
