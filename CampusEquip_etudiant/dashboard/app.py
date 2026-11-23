"""Console CampusEquip — analyses en lecture seule, stress tests isolés et temporaires.

    python -m dashboard.app --port 5055

Les pages analytiques ouvrent une session PostgreSQL READ ONLY. Le banc de
charge crée son propre schéma temporaire et ne touche pas aux données métier.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, g, jsonify, render_template, request, send_file

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402
from psycopg2.extras import RealDictCursor  # noqa: E402

from dashboard import donnees, graphiques, gps_simulator  # noqa: E402
from etudiant import config, depot  # noqa: E402

app = Flask(__name__, template_folder='templates', static_folder='static')
app.jinja_env.globals['graphiques'] = graphiques
_stress_lock = threading.Lock()
_stress_runs: dict[str, dict] = {}
_stress_rates = {10, 100, 1000, 10000}
_stress_max_duration = 60

MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
        'septembre', 'octobre', 'novembre', 'décembre')

LIBELLES_MOTIFS = {
    'CLE_LIGNE_EN_CONFLIT': 'Conflit de clé',
    'ENTETE_CONTRAT_CONTRADICTOIRE': 'En-tête contradictoire',
    'CONTRAT_EN_QUARANTAINE': 'Contrat isolé',
    'EQUIPEMENT_INCONNU': 'Équipement inconnu',
    'CLIENT_INCONNU': 'Client inconnu',
    'SITE_INCONNU': 'Site inconnu',
    'QUANTITY_INVALIDE': 'Quantité invalide',
    'DURATION_INVALIDE': 'Durée invalide',
    'UNIT_INVALIDE': 'Unité invalide',
    'UNIT_RATE_INVALIDE': 'Tarif invalide',
    'START_DATE_INVALIDE': 'Date invalide',
    'STATUS_INVALIDE': 'Statut invalide',
    'CONTRACT_ID_INVALIDE': 'Contrat invalide',
    'LINE_NO_INVALIDE': 'N° de ligne invalide',
    'EQUIPMENT_ID_INVALIDE': 'Équipement invalide',
    'COLONNES_INCOHERENTES': 'Colonnes incohérentes',
}


def libelle_motif(code: str) -> str:
    return LIBELLES_MOTIFS.get(code, code.replace('_', ' ').capitalize())


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------
def cnx():
    if 'cnx' not in g:
        g.cnx = donnees.connexion(config.parametres_connexion())
    return g.cnx


@app.teardown_appcontext
def fermer(exception=None):
    connexion = g.pop('cnx', None)
    if connexion is not None:
        try:
            connexion.rollback()
        finally:
            connexion.close()


def curseur():
    return cnx().cursor(cursor_factory=RealDictCursor)


# ---------------------------------------------------------------------------
# Filtres de mise en forme
# ---------------------------------------------------------------------------
@app.template_filter('montant')
def filtre_montant(valeur) -> str:
    if valeur in (None, ''):
        return '—'
    return f'{float(valeur):,.0f}'.replace(',', '\u202f')


@app.template_filter('decimales')
def filtre_decimales(valeur, chiffres: int = 2) -> str:
    if valeur in (None, ''):
        return '—'
    return f'{float(valeur):,.{chiffres}f}'.replace(',', '\u202f').replace('.', ',')


@app.template_filter('pourcent')
def filtre_pourcent(valeur) -> str:
    if valeur in (None, ''):
        return '—'
    return f'{float(valeur):.1f}'.replace('.', ',') + ' %'


@app.template_filter('datefr')
def filtre_datefr(valeur) -> str:
    if valeur in (None, ''):
        return '—'
    if isinstance(valeur, datetime):
        return valeur.strftime('%d/%m/%Y %H:%M')
    if isinstance(valeur, date):
        return valeur.strftime('%d/%m/%Y')
    return str(valeur)


@app.template_filter('jourfr')
def filtre_jourfr(valeur) -> str:
    if isinstance(valeur, date):
        return f'{valeur.day} {MOIS[valeur.month - 1]} {valeur.year}'
    return str(valeur)


@app.template_filter('heurefr')
def filtre_heurefr(valeur) -> str:
    if isinstance(valeur, datetime):
        return valeur.strftime('%d/%m · %H:%M')
    return str(valeur)


# ---------------------------------------------------------------------------
# Contexte de page
# ---------------------------------------------------------------------------
def _date(texte: str | None, defaut: date) -> date:
    if not texte:
        return defaut
    try:
        return date.fromisoformat(texte)
    except ValueError:
        return defaut


def filtres_courants(cur) -> donnees.Filtres:
    debut_min, fin_max = donnees.bornes(cur)
    debut = _date(request.args.get('debut'), debut_min)
    fin = _date(request.args.get('fin'), fin_max)
    if debut > fin:
        debut, fin = fin, debut
    campus_texte = request.args.get('campus', '')
    campus_id = int(campus_texte) if campus_texte.isdigit() else None
    return donnees.Filtres(debut, fin, campus_id)


def contexte(cur, filtres: donnees.Filtres) -> dict:
    liste = donnees.campus(cur)
    liens = {'debut': filtres.debut.isoformat(), 'fin': filtres.fin.isoformat()}
    if filtres.campus_id:
        liens['campus'] = filtres.campus_id
    return {
        'filtres': filtres,
        'liens': liens,
        'campus_liste': liste,
        'campus_courant': next((c for c in liste if c['campus_id'] == filtres.campus_id), None),
        'sante': donnees.sante(cur),
        'aujourdhui': datetime.now(),
    }


def _cumul(valeurs: list[float]) -> list[float]:
    total, sortie = 0.0, []
    for valeur in valeurs:
        total += valeur
        sortie.append(round(total, 2))
    return sortie


def _copie_stress(job: dict) -> dict:
    return {cle: valeur for cle, valeur in job.items() if not cle.startswith('_')}


def _creer_schema_stress(schema: str) -> None:
    connexion = psycopg2.connect(**config.parametres_connexion())
    try:
        with connexion.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        connexion.commit()
        depot.schema(connexion)
    except Exception:
        connexion.rollback()
        raise
    finally:
        connexion.close()


def _ouvrir_schema_stress(schema: str):
    connexion = psycopg2.connect(**config.parametres_connexion())
    try:
        with connexion.cursor() as cur:
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        connexion.commit()
        return connexion
    except Exception:
        connexion.close()
        raise


def _supprimer_schema_stress(schema: str) -> None:
    connexion = psycopg2.connect(**config.parametres_connexion())
    try:
        connexion.autocommit = True
        with connexion.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE')
                        .format(sql.Identifier(schema)))
    finally:
        connexion.close()


def _maj_stress(job_id: str, **champs) -> None:
    with _stress_lock:
        job = _stress_runs.get(job_id)
        if job is not None:
            job.update(champs)


def _lancer_stress_arriere_plan(job_id: str, schema: str, arret: threading.Event,
                                debits: list[int], duree: int) -> None:
    from outils import stress

    def progression(mesures: dict) -> None:
        _maj_stress(job_id, mesures=mesures, maj_le=datetime.now().isoformat())

    try:
        _maj_stress(job_id, statut='en_cours')
        resultat = stress.executer(
            debits, duree,
            connexion_factory=lambda: _ouvrir_schema_stress(schema),
            on_progress=progression,
            stop_event=arret)
        resultat['schema_isole'] = schema
        chemin = RACINE / 'resultats' / f'stress_{job_id}.json'
        chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = chemin.with_suffix('.json.tmp')
        temporaire.write_text(json.dumps(resultat, ensure_ascii=False, indent=2) + '\n',
                              encoding='utf-8')
        os.replace(temporaire, chemin)
        _maj_stress(
            job_id, statut='nettoyage', mesures=resultat, rapport=str(chemin),
            termine_le=datetime.now().isoformat())
    except Exception as erreur:
        app.logger.exception('Échec du stress test %s', job_id)
        _maj_stress(job_id, statut='echec',
                    erreur=f'{type(erreur).__name__}: {erreur}',
                    termine_le=datetime.now().isoformat())
    finally:
        try:
            _supprimer_schema_stress(schema)
            with _stress_lock:
                execution = _stress_runs.get(job_id)
                if execution is not None and execution['statut'] == 'nettoyage':
                    execution['statut'] = 'arrete' if arret.is_set() else 'termine'
        except Exception as erreur:
            app.logger.exception('Nettoyage du schéma de stress %s impossible', schema)
            _maj_stress(job_id, statut='echec',
                        erreur=f"Nettoyage PostgreSQL impossible : {type(erreur).__name__}: {erreur}")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route('/')
def accueil():
    with curseur() as cur:
        filtres = filtres_courants(cur)
        contexte_page = contexte(cur, filtres)
        indicateurs = donnees.kpis(cur, filtres)
        serie = donnees.serie_journaliere(cur, filtres)
        unites = donnees.par_unite(cur, filtres)
        campus = donnees.par_campus(cur, filtres)
        equipements = donnees.top_equipements(cur, filtres, 7)
        etapes = donnees.etapes_pipeline(cur)
        flux = donnees.flux_activite(cur, 8)
        matrice = donnees.matrice_campus_jour(cur, filtres)
        categories = donnees.categories_arbre(cur, filtres)
        qualite = donnees.qualite(cur)
        journal = donnees.lots(cur, 5)

    part_heure = (float(unites['heure'][1] / unites['total'] * 100)
                  if unites['total'] else 0.0)
    total_categories = sum(racine['montant'] for racine in categories) or 1
    montants = serie['montant']
    moyenne_jour = sum(montants) / len(montants) if montants else 0
    meilleur_jour = (max(montants), serie['etiquettes'][montants.index(max(montants))]) \
        if montants else (0, '—')

    vues = {
        'jour': graphiques.aire(serie['etiquettes'], serie['montant']),
        'cumul': graphiques.aire(serie['etiquettes'], _cumul(serie['montant'])),
    }

    return render_template(
        'accueil.html', page='accueil', titre='Console de pilotage',
        sous='Montants, qualité et flux de traitement en un seul écran',
        indicateurs=indicateurs, serie=serie, unites=unites, part_heure=part_heure,
        campus=campus, equipements=equipements, etapes=etapes, flux=flux,
        jauge=graphiques.jauge(float(qualite['taux'])),
        chaleur=graphiques.carte_chaleur(matrice['campus'], matrice['jours'],
                                         matrice['valeurs']),
        soleil=graphiques.soleil(categories) if categories else '',
        categories=categories, total_categories=total_categories,
        frise=graphiques.frise([
            {'titre': 'Lots reçus', 'valeur': etapes['lots'],
             'detail': f"{etapes['refuses']} refusé(s)", 'ton': graphiques.CYAN},
            {'titre': 'Lignes lues', 'valeur': etapes['recues'],
             'detail': f"{etapes['doublons']} doublon(s)", 'ton': graphiques.BLEU},
            {'titre': 'Contrôlées', 'valeur': etapes['acceptees'] + etapes['rejetees'],
             'detail': f"{etapes['anomalies']} anomalie(s)", 'ton': graphiques.VIOLET},
            {'titre': 'Chargées', 'valeur': etapes['acceptees'],
             'detail': 'en base', 'ton': graphiques.VERT},
            {'titre': 'Quarantaine', 'valeur': etapes['rejetees'],
             'detail': 'contrats isolés', 'ton': graphiques.ROSE},
        ]),
        vues=vues, qualite=qualite, journal=journal,
        moyenne_jour=moyenne_jour, meilleur_jour=meilleur_jour,
        **contexte_page)


@app.route('/contrats')
def contrats():
    recherche = (request.args.get('q') or '').strip() or None
    statut = request.args.get('statut') or None
    if statut not in (None, 'paid', 'closed', 'draft', 'cancelled'):
        statut = None
    with curseur() as cur:
        filtres = filtres_courants(cur)
        contexte_page = contexte(cur, filtres)
        lignes = donnees.contrats(cur, filtres, 40, recherche, statut)
        total = donnees.kpis(cur, filtres)
    return render_template('contrats.html', page='contrats', titre='Contrats',
                           sous='Parcourir la période, ouvrir un contrat au grain de la ligne',
                           contrats=lignes, total=total, recherche=recherche,
                           statut=statut, **contexte_page)


@app.route('/contrat/<int:contract_id>')
def contrat(contract_id: int):
    with curseur() as cur:
        filtres = filtres_courants(cur)
        contexte_page = contexte(cur, filtres)
        detail = donnees.contrat(cur, contract_id)
        if detail is None:
            abort(404)
    return render_template('contrat.html', page='contrats',
                           titre=f'Contrat {contract_id}',
                           sous='Chaque ligne est recalculable à la main',
                           detail=detail, **contexte_page)


@app.route('/qualite')
def qualite():
    with curseur() as cur:
        filtres = filtres_courants(cur)
        contexte_page = contexte(cur, filtres)
        indicateurs = donnees.qualite(cur)
        causes = donnees.motifs_rejet(cur, 7)
        rejets = donnees.rejets(cur, 60)
        anomalies = donnees.anomalies(cur, 20)
        journal = donnees.lots(cur, 20)
    return render_template(
        'qualite.html', page='qualite', titre='Qualité des données',
        sous='Contrats isolés, motifs de rejet et seuil d’alerte',
        indicateurs=indicateurs, causes=causes, rejets=rejets, anomalies=anomalies,
        journal=journal,
        jauge=graphiques.jauge(float(indicateurs['taux'])),
        motifs=graphiques.barres_horizontales(
            [(libelle_motif(ligne['code']), float(ligne['lignes']),
              graphiques.PALETTE[4] if 'CONTRAT' in ligne['code'] else graphiques.CYAN)
             for ligne in causes]),
        **contexte_page)


@app.route('/laboratoire')
def laboratoire():
    with curseur() as cur:
        filtres = filtres_courants(cur)
        contexte_page = contexte(cur, filtres)
        points = donnees.points_iot(cur, 200)
        categories = donnees.categories_arbre(cur, filtres)
        lots = donnees.lots(cur, 12)
        etapes = donnees.etapes_pipeline(cur)
    mesures = _lire_mesures_index()
    return render_template(
        'laboratoire.html', page='laboratoire', titre='Laboratoire',
        sous='Les quatre bonus mesurés, branchés sur la vraie base',
        mesures=mesures, points=points, categories=categories,
        total_categories=sum(racine['montant'] for racine in categories) or 1,
        nuage=graphiques.nuage_iot(points) if points else '',
        lots=[lot for lot in lots if lot['status'] == 'CHARGE'],
        etapes=etapes,
        **contexte_page)


@app.route('/stress')
def stress():
    with curseur() as cur:
        contexte_page = contexte(cur, filtres_courants(cur))
    return render_template(
        'stress.html', page='stress', titre='Stress test',
        sous='Mesurer le pipeline en temps réel, dans un schéma PostgreSQL isolé',
        **contexte_page)


@app.route('/iot-lab')
def iot_lab():
    with curseur() as cur:
        contexte_page = contexte(cur, filtres_courants(cur))
    return render_template(
        'iot_lab.html', page='iot_lab', titre='IoT Lab',
        sous='Construisez un circuit, câblez-le et observez le comportement simulé',
        **contexte_page)


@app.route('/gps')
def gps():
    with curseur() as cur:
        contexte_page = contexte(cur, filtres_courants(cur))
    return render_template(
        'gps.html', page='gps', titre='GPS Fleet',
        sous='Flotte connectée · télémétrie simulée en temps réel',
        **contexte_page)


@app.route('/lots')
def lots():
    with curseur() as cur:
        filtres = filtres_courants(cur)
        contexte_page = contexte(cur, filtres)
        journal = donnees.lots(cur, 40)
        indicateurs = donnees.qualite(cur)
        flux = donnees.flux_activite(cur, 10)
        iot = donnees.observations_iot(cur)
    return render_template('lots.html', page='lots', titre='Lots & exécutions',
                           sous='Journal du rejeu, état de la base et source IoT',
                           journal=journal, indicateurs=indicateurs, flux=flux,
                           iot=iot, **contexte_page)


# ---------------------------------------------------------------------------
# API (fragments et mesures)
# ---------------------------------------------------------------------------
def _gps_write_origin_allowed():
    origin = request.headers.get('Origin')
    return not origin or urlsplit(origin).netloc == request.host


@app.route('/api/gps/snapshot')
def api_gps_snapshot():
    try:
        return jsonify({'ok': True, **gps_simulator.snapshot()})
    except psycopg2.Error:
        app.logger.exception('PostgreSQL unavailable while reading GPS simulation')
        return jsonify({'ok': False, 'erreur': 'La télémétrie GPS est temporairement indisponible.'}), 503


@app.route('/api/gps/step', methods=['POST'])
def api_gps_step():
    if not _gps_write_origin_allowed():
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403
    try:
        return jsonify({'ok': True, **gps_simulator.step()})
    except psycopg2.Error:
        app.logger.exception('PostgreSQL unavailable while advancing GPS simulation')
        return jsonify({'ok': False, 'erreur': 'La télémétrie GPS est temporairement indisponible.'}), 503


@app.route('/api/gps/control', methods=['POST'])
def api_gps_control():
    if not request.is_json:
        return jsonify({'ok': False, 'erreur': 'envoyez les paramètres en JSON'}), 415
    if not _gps_write_origin_allowed():
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'ok': False, 'erreur': 'objet JSON attendu'}), 400
    try:
        result = gps_simulator.control(payload.get('action'), payload.get('speed_multiplier'))
        return jsonify({'ok': True, **result})
    except gps_simulator.GpsInputError as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur)}), 400
    except psycopg2.Error:
        app.logger.exception('PostgreSQL unavailable while controlling GPS simulation')
        return jsonify({'ok': False, 'erreur': 'La télémétrie GPS est temporairement indisponible.'}), 503


@app.route('/api/gps/geofences', methods=['POST'])
def api_gps_create_geofence():
    if not request.is_json:
        return jsonify({'ok': False, 'erreur': 'envoyez les paramètres en JSON'}), 415
    if not _gps_write_origin_allowed():
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403
    try:
        fence = gps_simulator.add_geofence(request.get_json(silent=True))
        return jsonify({'ok': True, 'geofence': fence}), 201
    except gps_simulator.GpsInputError as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur)}), 400
    except psycopg2.Error:
        app.logger.exception('PostgreSQL unavailable while creating GPS geofence')
        return jsonify({'ok': False, 'erreur': 'La télémétrie GPS est temporairement indisponible.'}), 503


@app.route('/api/gps/geofences/<int:geofence_id>', methods=['DELETE'])
def api_gps_delete_geofence(geofence_id: int):
    if not _gps_write_origin_allowed():
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403
    try:
        if not gps_simulator.delete_geofence(geofence_id):
            return jsonify({'ok': False, 'erreur': 'Zone géographique introuvable.'}), 404
        return jsonify({'ok': True})
    except psycopg2.Error:
        app.logger.exception('PostgreSQL unavailable while deleting GPS geofence')
        return jsonify({'ok': False, 'erreur': 'La télémétrie GPS est temporairement indisponible.'}), 503


@app.route('/api/sante')
def api_sante():
    try:
        with curseur() as cur:
            return jsonify({'ok': True, **donnees.sante(cur)})
    except psycopg2.Error as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur).strip()}), 503


@app.route('/api/flux')
def api_flux():
    try:
        with curseur() as cur:
            flux = donnees.flux_activite(cur, 8)
        return jsonify({'ok': True, 'html': render_template('_flux.html', flux=flux)})
    except psycopg2.Error as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur).strip()}), 503


@app.route('/api/prototype/snapshot')
def api_prototype_snapshot():
    """Expose project records to the local UI."""
    from dashboard.prototype import lire_instantane

    try:
        with curseur() as cur:
            instantane = lire_instantane(cur)
        return jsonify({'ok': True, **instantane})
    except psycopg2.Error as erreur:
        app.logger.warning('PostgreSQL prototype read unavailable: %s', erreur)
        return jsonify({
            'ok': False,
            'erreur': 'The CampusEquip PostgreSQL data source is unavailable.',
        }), 503


@app.route('/api/prototype/events', methods=['POST'])
def api_prototype_create_return():
    """Record a return event through the axes 3-4 ingestion pipeline."""
    if not request.is_json:
        return jsonify({'ok': False, 'erreur': 'envoyez les paramètres en JSON'}), 415
    origine = request.headers.get('Origin')
    if origine and urlsplit(origine).netloc != request.host:
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403

    valeurs = request.get_json(silent=True)
    if not isinstance(valeurs, dict):
        return jsonify({'ok': False, 'erreur': 'objet JSON attendu'}), 400
    contract_id = valeurs.get('contract_id')
    event_id = valeurs.get('event_id')
    condition = valeurs.get('condition')
    notes = valeurs.get('notes', '')
    observed_at = valeurs.get('observed_at')
    if type(contract_id) is not int or contract_id <= 0:
        return jsonify({'ok': False, 'erreur': 'contract_id doit être un entier positif'}), 400
    if not isinstance(event_id, str) or not event_id:
        return jsonify({'ok': False, 'erreur': 'event_id absent'}), 400
    if not isinstance(condition, str) or condition not in {
            'Excellent', 'Good', 'Fair', 'Needs repair'}:
        return jsonify({'ok': False, 'erreur': 'condition de retour invalide'}), 400
    if not isinstance(notes, str) or len(notes) > 500:
        return jsonify({'ok': False, 'erreur': 'notes doivent être du texte de 500 caractères maximum'}), 400
    if observed_at is not None and not isinstance(observed_at, str):
        return jsonify({'ok': False, 'erreur': 'observed_at doit être une date UTC au format ISO'}), 400

    from axes_3_4.pipeline import enregistrer_retour_interactif
    from pymongo.errors import PyMongoError

    try:
        resultat = enregistrer_retour_interactif(
            contract_id, event_id, condition, notes, observed_at,
        )
    except LookupError as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur)}), 404
    except ValueError as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur)}), 400
    except psycopg2.Error as erreur:
        app.logger.exception('PostgreSQL unavailable while recording a return event')
        return jsonify({
            'ok': False,
            'erreur': 'PostgreSQL is unavailable; the return event was not confirmed.',
        }), 503
    except PyMongoError:
        app.logger.exception('MongoDB unavailable while recording a return event')
        return jsonify({
            'ok': False,
            'erreur': 'MongoDB could not confirm the event. Refresh event history before retrying.',
        }), 503
    return jsonify({'ok': True, **resultat}), 201


@app.route('/api/stress/start', methods=['POST'])
def api_stress_start():
    if not request.is_json:
        return jsonify({'ok': False, 'erreur': 'envoyez les paramètres en JSON'}), 415
    origine = request.headers.get('Origin')
    if origine and urlsplit(origine).netloc != request.host:
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403

    parametres = request.get_json(silent=True)
    debits = parametres.get('debits') if isinstance(parametres, dict) else None
    duree = parametres.get('duree') if isinstance(parametres, dict) else None
    if (not isinstance(debits, list) or not debits
            or any(type(debit) is not int or debit not in _stress_rates for debit in debits)
            or len(set(debits)) != len(debits)):
        return jsonify({
            'ok': False,
            'erreur': 'choisissez un ou plusieurs débits distincts parmi 10, 100, 1 000 et 10 000 événements/s',
        }), 400
    if type(duree) is not int or not 1 <= duree <= _stress_max_duration:
        return jsonify({
            'ok': False,
            'erreur': f'la durée de chaque palier doit être entre 1 et {_stress_max_duration} secondes',
        }), 400

    with _stress_lock:
        if any(job['statut'] in {
                'preparation', 'en_cours', 'arret_demande', 'nettoyage'}
               for job in _stress_runs.values()):
            return jsonify({'ok': False, 'erreur': 'un stress test est déjà en cours'}), 409
        job_id = uuid.uuid4().hex
        schema = f'ce_stress_{job_id}'
        arret = threading.Event()
        _stress_runs[job_id] = {
            'id': job_id, 'statut': 'preparation', 'debits': debits,
            'duree_palier_s': duree, 'mesures': None, 'erreur': None,
            'rapport': None, 'cree_le': datetime.now().isoformat(),
            '_schema': schema, '_arret': arret,
        }

    try:
        _creer_schema_stress(schema)
    except Exception as erreur:
        app.logger.exception('Impossible de préparer le schéma isolé pour le stress test')
        try:
            _supprimer_schema_stress(schema)
        except Exception:
            app.logger.exception('Nettoyage du schéma de stress incomplet %s', schema)
        _maj_stress(job_id, statut='echec',
                    erreur=f'{type(erreur).__name__}: {erreur}')
        return jsonify({'ok': False, 'erreur': str(erreur)}), 503

    with _stress_lock:
        for ancien_id in list(_stress_runs)[:-5]:
            if _stress_runs[ancien_id]['statut'] in {'termine', 'arrete', 'echec'}:
                del _stress_runs[ancien_id]
        thread = threading.Thread(
            target=_lancer_stress_arriere_plan, args=(job_id, schema, arret, debits, duree),
            name=f'campusequip-stress-{job_id[:8]}', daemon=True)
        thread.start()
    with _stress_lock:
        reponse = _copie_stress(_stress_runs[job_id])
    return jsonify({'ok': True, 'execution': reponse}), 202


@app.route('/api/stress/<job_id>')
def api_stress_status(job_id: str):
    with _stress_lock:
        execution = _stress_runs.get(job_id)
        if execution is None:
            return jsonify({'ok': False, 'erreur': 'exécution inconnue ou expirée'}), 404
        return jsonify({'ok': True, 'execution': _copie_stress(execution)})


@app.route('/api/stress/<job_id>/stop', methods=['POST'])
def api_stress_stop(job_id: str):
    origine = request.headers.get('Origin')
    if origine and urlsplit(origine).netloc != request.host:
        return jsonify({'ok': False, 'erreur': 'origine de requête refusée'}), 403
    with _stress_lock:
        execution = _stress_runs.get(job_id)
        if execution is None:
            return jsonify({'ok': False, 'erreur': 'exécution inconnue ou expirée'}), 404
        if execution['statut'] not in {'preparation', 'en_cours'}:
            return jsonify({'ok': False, 'erreur': 'cette exécution n’est plus active'}), 409
        execution['_arret'].set()
        execution['statut'] = 'arret_demande'
        return jsonify({'ok': True, 'execution': _copie_stress(execution)})


@app.route('/api/stress/<job_id>/rapport')
def api_stress_rapport(job_id: str):
    with _stress_lock:
        execution = _stress_runs.get(job_id)
        chemin = execution.get('rapport') if execution else None
    if not chemin or not Path(chemin).is_file():
        return jsonify({'ok': False, 'erreur': 'rapport indisponible'}), 404
    return send_file(chemin, as_attachment=True,
                     download_name=f'stress_{job_id}.json',
                     mimetype='application/json')


@app.route('/api/morceaux')
def api_morceaux():
    """Bonus 3 : lecture par morceaux comparée à la lecture complète."""
    from bonus.lecture_morceaux import analyser_par_morceaux, empreinte_decisions
    from etudiant import traitement

    try:
        numero = int(request.args.get('lot', '1'))
        taille = max(1, min(int(request.args.get('taille', '200')), 5000))
    except ValueError:
        return jsonify({'ok': False, 'erreur': 'paramètres invalides'}), 400

    dossier = RACINE / 'flux_demo' / f'lot_{numero:06d}'
    if not dossier.is_dir():
        return jsonify({'ok': False,
                        'erreur': f'lot {numero:06d} absent de flux_demo'}), 404
    manifeste = json.loads((dossier / 'manifest.json').read_text(encoding='utf-8'))

    debut = time.perf_counter()
    complet = traitement.preparer_lot(dossier, manifeste).analyse
    duree_complet = (time.perf_counter() - debut) * 1000

    debut = time.perf_counter()
    morceaux, stats = analyser_par_morceaux(dossier, manifeste, taille)
    duree = (time.perf_counter() - debut) * 1000

    return jsonify({
        'ok': True,
        'lot': numero,
        'taille': stats['taille'],
        'morceaux': stats['morceaux'],
        'lignes': stats['lignes'],
        'decisions': len(complet.lignes),
        'identique': empreinte_decisions(morceaux) == empreinte_decisions(complet),
        'duree_ms': round(duree, 1),
        'duree_complet_ms': round(duree_complet, 1),
    })


@app.route('/api/precalcul')
def api_precalcul():
    """Bonus 2 : précalcul matérialisé contre calcul à la demande."""
    try:
        with curseur() as cur:
            debut = time.perf_counter()
            cur.execute("""
                SELECT sum(line_amount) AS total, count(*) AS lignes
                FROM v_lignes_retenues
            """)
            demande = cur.fetchone()
            ms_demande = (time.perf_counter() - debut) * 1000

            debut = time.perf_counter()
            cur.execute('SELECT sum(montant) AS total, count(*) AS cellules '
                        'FROM mv_montant_jour_campus')
            precalcul = cur.fetchone()
            ms_precalcul = (time.perf_counter() - debut) * 1000
        cnx().rollback()
    except psycopg2.Error as erreur:
        return jsonify({'ok': False, 'erreur': str(erreur).strip()}), 503

    maximum = max(ms_demande, ms_precalcul, 0.1)
    return jsonify({
        'ok': True,
        'ms_demande': round(ms_demande, 2),
        'ms_precalcul': round(ms_precalcul, 2),
        'largeur_demande': round(ms_demande / maximum * 100, 1),
        'largeur_precalcul': round(ms_precalcul / maximum * 100, 1),
        'total_demande': f"{float(demande['total'] or 0):,.0f}".replace(',', '\u202f'),
        'cellules': int(precalcul['cellules'] or 0),
        'egal': (demande['total'] or 0) == (precalcul['total'] or 0),
    })


def _lire_mesures_index() -> dict | None:
    chemin = RACINE / 'preuves' / 'index_mesures.json'
    if not chemin.is_file():
        return None
    try:
        return json.loads(chemin.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Erreurs
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def page_absente(erreur):
    return render_template('erreur.html', titre='Page introuvable',
                           message='Ce contrat ou cette page n’existe pas.',
                           detail='Vérifiez l’identifiant demandé.',
                           sante={'base': config.nom_base(), 'version': '—'}), 404


@app.errorhandler(psycopg2.Error)
def base_injoignable(erreur):
    return render_template('erreur.html', titre='Base injoignable',
                           message='La console ne peut pas lire PostgreSQL.',
                           detail=str(erreur).strip(),
                           sante={'base': config.nom_base(), 'version': '—'}), 503


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port', type=int, default=5055)
    p.add_argument('--hote', default='127.0.0.1')
    p.add_argument('--debug', action='store_true')
    arguments = p.parse_args()
    config.charger_env()
    print(f'CampusEquip — console sur http://{arguments.hote}:{arguments.port}')
    print(f'Base : {config.nom_base()}')
    app.run(host=arguments.hote, port=arguments.port, debug=arguments.debug,
            use_reloader=arguments.debug)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
