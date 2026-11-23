#!/bin/sh
# =====================================================================
#  Point d'entrée du conteneur CampusEquip.
#
#    console   (défaut) attend la base, l'initialise si elle est vide,
#              charge la démo, puis lance la console sur 0.0.0.0:5055
#    demo      régénère et recharge le jeu de démonstration
#    analyses  relance les trois analyses SQL
#    init      prépare la base (options transmises : --reinitialiser, --verifier)
#    tests     lance les 41 tests sur la base de test
#    <commande> exécute la commande telle quelle (ex. python -m outils.guide)
#
#  Le schéma n'est appliqué QUE si la base est vide : redémarrer le conteneur
#  ne doit jamais effacer les contrats déjà chargés.
# =====================================================================
set -eu

export PYTHONUNBUFFERED=1
: "${DATABASE_URL:?DATABASE_URL est requis (voir docker-compose.yml)}"

attendre_base() {
    printf 'Attente de PostgreSQL'
    essai=0
    while [ "$essai" -lt 60 ]; do
        if python - "$DATABASE_URL" <<'PY'
import sys
import psycopg2
try:
    psycopg2.connect(sys.argv[1], connect_timeout=3).close()
except Exception:
    raise SystemExit(1)
PY
        then
            echo ' — prêt.'
            return 0
        fi
        essai=$((essai + 1))
        printf '.'
        sleep 2
    done
    echo ' — échec : la base ne répond pas.'
    return 1
}

# Vrai (code 0) si la base ne contient aucun contrat — table absente comprise.
base_vide() {
    python - <<'PY'
import os
import sys
import psycopg2

try:
    cnx = psycopg2.connect(os.environ['DATABASE_URL'])
    with cnx.cursor() as cur:
        cur.execute('SELECT count(*) FROM contracts')
        vide = cur.fetchone()[0] == 0
    cnx.close()
except Exception:
    vide = True
sys.exit(0 if vide else 1)
PY
}

COMMANDE="${1:-console}"
case "$COMMANDE" in
    console)
        attendre_base
        if base_vide; then
            echo 'Base vide : application du schéma…'
            python -m outils.init_base
            if [ "${AUTO_DEMO:-1}" = "1" ]; then
                echo 'Chargement du jeu de démonstration (4 lots)…'
                python -m outils.demo --sans-reinitialiser
            fi
        else
            echo 'Base déjà initialisée : schéma et données conservés.'
        fi
        echo "Console CampusEquip sur http://0.0.0.0:${PORT:-5055}"
        exec python -m dashboard.app --hote 0.0.0.0 --port "${PORT:-5055}"
        ;;
    demo)
        attendre_base
        exec python -m outils.demo
        ;;
    analyses)
        attendre_base
        exec python -m outils.analyses
        ;;
    init)
        attendre_base
        shift
        exec python -m outils.init_base "$@"
        ;;
    tests)
        attendre_base
        exec python -m unittest discover -s tests -t . -v
        ;;
    *)
        exec "$@"
        ;;
esac
