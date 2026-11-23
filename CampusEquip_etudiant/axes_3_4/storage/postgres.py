"""Connexion PostgreSQL du socle avec fermeture explicite des connexions."""
from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def session():
    from etudiant.depot import connexion

    cnx = connexion()
    try:
        with cnx:
            yield cnx
    finally:
        cnx.close()
