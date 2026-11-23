"""Support commun des tests : base de test jetable et répertoires isolés.

Les tests ne touchent JAMAIS la base de démonstration : le nom de la base doit
finir par `_test`. Connexion par défaut :
    postgresql://postgres@127.0.0.1:5432/campusequip_test
surchargeable avec CAMPUSEQUIP_TEST_URL.
"""
from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg2

RACINE = Path(__file__).resolve().parent.parent
TRAVAIL = RACINE / '.tests_tmp'          # dans le projet, ignoré par git

URL_TEST = os.environ.get('CAMPUSEQUIP_TEST_URL',
                          'postgresql://postgres@127.0.0.1:5432/campusequip_test')

if not urlsplit(URL_TEST).path.rstrip('/').endswith('_test'):
    raise RuntimeError(f'base de test refusée (nom inattendu) : {URL_TEST}')

os.environ['DATABASE_URL'] = URL_TEST

from etudiant import config, depot  # noqa: E402  (après la pose de DATABASE_URL)


def _url_maintenance(url: str) -> str:
    parties = urlsplit(url)
    return urlunsplit((parties.scheme, parties.netloc, '/postgres', parties.query,
                       parties.fragment))


def preparer_base() -> None:
    """Crée la base de test si besoin, puis applique le schéma."""
    cnx = psycopg2.connect(_url_maintenance(URL_TEST))
    try:
        cnx.autocommit = True
        with cnx.cursor() as cur:
            cur.execute('SELECT 1 FROM pg_database WHERE datname = %s',
                        (urlsplit(URL_TEST).path.lstrip('/'),))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{urlsplit(URL_TEST).path.lstrip("/")}"')
    finally:
        cnx.close()
    cnx = depot.connexion()
    try:
        depot.schema(cnx)
    finally:
        cnx.close()


def reinitialiser_schema() -> None:
    cnx = depot.connexion()
    try:
        depot.schema(cnx)
    finally:
        cnx.close()


class BasePipeline(unittest.TestCase):
    """Classe de base : schéma neuf avant chaque test, sorties isolées."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._racine = TRAVAIL
        if cls._racine.exists():
            shutil.rmtree(cls._racine, ignore_errors=True)
        cls.rapports = cls._racine / 'rapports'
        cls.quarantaine = cls._racine / 'quarantaine'
        cls.lots = cls._racine / 'lots'
        for dossier in (cls.rapports, cls.quarantaine, cls.lots):
            dossier.mkdir(parents=True, exist_ok=True)
        os.environ['CAMPUSEQUIP_RAPPORTS'] = str(cls.rapports)
        os.environ['CAMPUSEQUIP_QUARANTAINE'] = str(cls.quarantaine)
        preparer_base()

    @classmethod
    def tearDownClass(cls) -> None:
        # Les fichiers restent sur disque pour inspection : .tests_tmp est
        # recréé au prochain lancement.
        pass

    def setUp(self) -> None:
        reinitialiser_schema()
        self.cnx = depot.connexion()

    def tearDown(self) -> None:
        self.cnx.close()

    # -- raccourcis de lecture -------------------------------------------
    def compter(self, table: str) -> int:
        return depot.compter(self.cnx, table)

    def valeur(self, requete: str, parametres=()):
        with self.cnx.cursor() as cur:
            cur.execute(requete, parametres)
            resultat = cur.fetchone()
        self.cnx.rollback()
        return resultat[0] if resultat else None

    def lignes(self, requete: str, parametres=()) -> list[tuple]:
        with self.cnx.cursor() as cur:
            cur.execute(requete, parametres)
            resultat = cur.fetchall()
        self.cnx.rollback()
        return resultat

    def journal(self, statut: str = 'CHARGE') -> list[tuple]:
        return self.lignes(
            'SELECT batch_number, status, rows_accepted, rows_rejected, rejection_rate '
            'FROM ingestion_batches WHERE status = %s ORDER BY batch_id', (statut,))


def dossier_lot(racine: Path, nom: str) -> Path:
    dossier = racine / nom
    return dossier
