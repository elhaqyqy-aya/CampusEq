"""Prépare une base PostgreSQL neuve pour CampusEquip.

Sans psql, ce lanceur crée la base, applique `etudiant/schema.sql`, puis
vérifie que les objets attendus existent.

    python -m outils.init_base                  # crée la base et le schéma
    python -m outils.init_base --reinitialiser  # supprime puis recrée la base
    python -m outils.init_base --verifier       # ne modifie rien, contrôle

La connexion vient de DATABASE_URL (voir etudiant/config.py). Aucun mot de
passe n'est écrit dans les fichiers du projet.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etudiant import config, depot  # noqa: E402

OBJETS_ATTENDUS = ('campus', 'sites', 'clients', 'categories', 'equipments',
                   'contracts', 'contract_lines', 'ingestion_batches',
                   'batch_rejections', 'batch_anomalies', 'lab_config',
                   'v_lignes_retenues')


def _url_avec_base(url: str, base: str) -> str:
    parties = urlsplit(url)
    return urlunsplit((parties.scheme, parties.netloc, '/' + base, parties.query,
                       parties.fragment))


def _nom_base(url: str) -> str:
    return urlsplit(url).path.lstrip('/') or 'campusequip'


def reinitialiser(url: str) -> None:
    """Vide la base cible (schéma public) avant de réappliquer le modèle.

    On ne supprime pas la base elle-même : vider le schéma suffit et évite de
    couper les connexions d'autres outils (pgAdmin, psql, tableau de bord).
    """
    creer_si_absente(url)
    cnx = psycopg2.connect(url)
    try:
        cnx.autocommit = True
        with cnx.cursor() as cur:
            cur.execute('DROP SCHEMA IF EXISTS public CASCADE')
            cur.execute('CREATE SCHEMA public')
    finally:
        cnx.close()


def creer_si_absente(url: str) -> bool:
    maintenance = _url_avec_base(url, 'postgres')
    cnx = psycopg2.connect(maintenance)
    try:
        cnx.autocommit = True
        with cnx.cursor() as cur:
            cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (_nom_base(url),))
            if cur.fetchone():
                return False
            cur.execute(f'CREATE DATABASE "{_nom_base(url)}"')
            return True
    finally:
        cnx.close()


def verifier(url: str) -> list[str]:
    with psycopg2.connect(url) as cnx:
        with cnx.cursor() as cur:
            cur.execute('SELECT relname FROM pg_class WHERE relkind IN (%s, %s)',
                        ('r', 'v'))
            existants = {ligne[0] for ligne in cur.fetchall()}
    return [nom for nom in OBJETS_ATTENDUS if nom not in existants]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--reinitialiser', action='store_true',
                   help='supprime la base cible avant de la recréer')
    p.add_argument('--verifier', action='store_true',
                   help='contrôle seulement la présence des objets')
    arguments = p.parse_args()

    config.charger_env()
    url = config.url_base()
    base = _nom_base(url)
    sans_mot_de_passe = url.replace(urlsplit(url).password or '', '***') \
        if urlsplit(url).password else url

    if arguments.verifier:
        manquants = verifier(url)
        if manquants:
            print(f'Objets manquants dans « {base} » : {", ".join(manquants)}')
            return 1
        print(f'Base « {base} » : {len(OBJETS_ATTENDUS)} objets attendus présents.')
        return 0

    if arguments.reinitialiser:
        print(f'Réinitialisation de la base « {base} »…')
        reinitialiser(url)
    else:
        creee = creer_si_absente(url)
        print(f"Base « {base} » {'créée' if creee else 'déjà présente'}.")

    with psycopg2.connect(url) as cnx:
        depot.schema(cnx)
    manquants = verifier(url)
    if manquants:
        print(f'Échec : objets manquants après application du schéma : {manquants}')
        return 1
    print(f'Schéma appliqué ({sans_mot_de_passe}). '
          f'{len(OBJETS_ATTENDUS)} objets vérifiés.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
