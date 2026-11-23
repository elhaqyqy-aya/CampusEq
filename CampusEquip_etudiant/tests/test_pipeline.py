"""Tests d'intégration du pipeline : chargement, quarantaine, rejeu, conflits.

Chaque test part d'un schéma vide, écrit un petit lot explicable, lance
`traiter_lot` puis vérifie ce qui est réellement en base.
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from psycopg2.extras import RealDictCursor

from dashboard.prototype import lire_postgresql
from etudiant import depot, regles, traitement
from tests import base, fabrique


class TestChargementValide(base.BasePipeline):
    def test_snapshot_financier_exclut_les_contrats_non_retenus(self):
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=2001, status='paid', duration=2,
                            unit_rate='10.00'),
             fabrique.ligne(contract_id=2002, status='cancelled', duration=1,
                            unit_rate='99.00')],
            lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)
        self.assertEqual(resultat['status'], 'CHARGE')

        with self.cnx.cursor(cursor_factory=RealDictCursor) as cur:
            snapshot = lire_postgresql(cur)

        campus = next(item for item in snapshot['campuses'] if item['id'] == 1)
        self.assertEqual(campus['amount'], '20.00')

    def test_montants_heure_et_journee_et_statuts(self):
        # Contrat 2001 (paid) : 2 h x 3 x 25 = 150 et 1 jour x 2 x 200 = 400.
        # Contrat 2002 (cancelled) : stocké, mais exclu des indicateurs.
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=2001, line_no=1, unit='hour', quantity=2,
                            duration=3, unit_rate='25.00'),
             fabrique.ligne(contract_id=2001, line_no=2, unit='day', quantity=1,
                            duration=2, unit_rate='200.00'),
             fabrique.ligne(contract_id=2002, line_no=1, status='cancelled',
                            quantity=1, duration=1, unit_rate='99.00')],
            lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(resultat['status'], 'CHARGE')
        self.assertEqual(resultat['lignes_ajoutees_en_base'], 3)
        self.assertEqual(self.compter('contracts'), 2)
        self.assertEqual(self.compter('contract_lines'), 3)
        self.assertEqual(self.valeur("SELECT sum(line_amount) FROM contract_lines "
                                     "WHERE contract_id = 2001"), Decimal('550.00'))
        self.assertEqual(depot.total_retenu(self.cnx, 2001), Decimal('550.00'))
        self.assertEqual(depot.total_retenu(self.cnx, 2002), Decimal('0.00'))
        self.assertEqual(self.valeur('SELECT status FROM contracts WHERE contract_id = 2002'),
                         'cancelled')


class TestQuarantaine(base.BasePipeline):
    def test_repetition_confirmee_et_conflit_de_cle(self):
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=10, line_no=1),
             fabrique.ligne(contract_id=10, line_no=1),           # copie exacte
             fabrique.ligne(contract_id=11, line_no=1, duration=2),
             fabrique.ligne(contract_id=11, line_no=1, duration=3),  # conflit de clé
             fabrique.ligne(contract_id=11, line_no=2)],
            lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(resultat['doublons_retires'], 1)
        self.assertEqual(resultat['lignes_recues'], 5)
        self.assertEqual(resultat['lignes_acceptees'], 1)
        self.assertEqual(resultat['lignes_rejetees'], 3)
        self.assertEqual(resultat['contrats_acceptes'], 1)
        self.assertEqual(resultat['contrats_rejetes'], 1)
        self.assertEqual(self.compter('contracts'), 1)
        self.assertEqual(self.compter('contract_lines'), 1)
        self.assertEqual(self.compter('batch_rejections'), 3)

    def test_structure_invalide_refusee_avant_ecriture(self):
        # En-tête avec deux colonnes interverties : le lot est refusé.
        entetes = list(fabrique.COLONNES)
        entetes[1], entetes[2] = entetes[2], entetes[1]
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [['1', '1', '1', '2026-11-02', 'paid', '1', '1', '1', 'hour', '2', '10.00']],
            entetes=entetes, lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(resultat['status'], 'REJETE_STRUCTURE')
        self.assertIn('en-tête refusé', resultat['motif'])
        self.assertEqual(self.compter('contracts'), 0)
        self.assertEqual(self.compter('contract_lines'), 0)
        self.assertEqual(len(self.journal('REJETE_STRUCTURE')), 1)

    def test_colonne_supplementaire_refusee(self):
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [['1', '1', '1', '2026-11-02', 'paid', '1', '1', '1', 'hour', '2', '10.00', 'x']],
            entetes=fabrique.COLONNES + ['commentaire'], lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)
        self.assertEqual(resultat['status'], 'REJETE_STRUCTURE')
        self.assertEqual(self.compter('contracts'), 0)

    def test_manifeste_incoherent_avec_les_fichiers(self):
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=1)], lot=1)
        manifeste['rows'] = 2                       # le manifeste ment
        (dossier / 'manifest.json').write_text(__import__('json').dumps(manifeste))
        resultat = traitement.traiter_lot(dossier, manifeste)
        self.assertEqual(resultat['status'], 'REJETE_STRUCTURE')
        self.assertIn('annonce 2 lignes', resultat['motif'])

    def test_quantite_invalide_et_quantite_25(self):
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=20, quantity=-1),
             fabrique.ligne(contract_id=21, quantity=25)],
            lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(resultat['contrats_acceptes'], 1)
        self.assertEqual(resultat['contrats_rejetes'], 1)
        self.assertEqual(resultat['anomalies'], 1)
        self.assertEqual(resultat['lignes_rejetees'], 1)
        self.assertEqual(self.compter('batch_anomalies'), 1)
        # La quantité 25 est acceptée : elle ne doit pas être un rejet.
        self.assertEqual(self.valeur('SELECT quantity FROM contract_lines '
                                     'WHERE contract_id = 21'), 25)

    def test_une_ligne_invalide_isole_toutes_les_lignes_du_contrat(self):
        # Ligne 1 valide, ligne 2 invalide : les DEUX partent en quarantaine,
        # le contrat ne doit pas être chargé partiellement.
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=40, line_no=1, duration=2),
             fabrique.ligne(contract_id=40, line_no=2, duration=-3),
             fabrique.ligne(contract_id=41, line_no=1, duration=2)],
            lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(resultat['lignes_rejetees'], 2)
        self.assertEqual(resultat['lignes_acceptees'], 1)
        self.assertEqual(resultat['contrats_acceptes'], 1)
        self.assertEqual(self.compter('contracts'), 1)
        self.assertEqual(self.valeur('SELECT contract_id FROM contracts'), 41)
        motifs = [ligne[0] for ligne in
                  self.lignes('SELECT unnest(motifs) FROM batch_rejections ORDER BY position')]
        self.assertTrue(any(motif.startswith('CONTRAT_EN_QUARANTAINE') for motif in motifs),
                        motifs)
        self.assertTrue(any(motif.startswith('DURATION_INVALIDE') for motif in motifs), motifs)

    def test_entete_contradictoire_et_reference_inconnue(self):
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'),
            [fabrique.ligne(contract_id=30, line_no=1, status='paid'),
             fabrique.ligne(contract_id=30, line_no=2, status='draft'),
             fabrique.ligne(contract_id=31, line_no=1, equipment_id=999)],
            lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)
        self.assertEqual(resultat['lignes_acceptees'], 0)
        self.assertEqual(resultat['lignes_rejetees'], 3)
        self.assertEqual(self.compter('contracts'), 0)
        motifs = ' '.join(ligne[0] for ligne in
                          self.lignes('SELECT unnest(motifs) FROM batch_rejections'))
        self.assertIn('ENTETE_CONTRAT_CONTRADICTOIRE', motifs)
        self.assertIn('EQUIPEMENT_INCONNU', motifs)


class TestRejeuEtConflit(base.BasePipeline):
    def _lot_propre(self, nom='lot_000001', contrat=100):
        return fabrique.ecrire_lot(
            base.dossier_lot(self.lots, nom),
            [fabrique.ligne(contract_id=contrat, line_no=1)], lot=1)

    def test_rejeu_identique_ne_double_rien(self):
        dossier, manifeste = self._lot_propre()
        premier = traitement.traiter_lot(dossier, manifeste)
        self.assertEqual(premier['status'], 'CHARGE')
        second = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(second['status'], 'DEJA_CHARGE')
        self.assertEqual(second['lignes_ajoutees_en_base'], 0)
        self.assertEqual(self.compter('contracts'), 1)
        self.assertEqual(self.compter('contract_lines'), 1)
        self.assertEqual(len(self.journal('CHARGE')), 1)

    def test_dossier_renomme_reconnu_comme_rejeu(self):
        dossier, manifeste = self._lot_propre()
        traitement.traiter_lot(dossier, manifeste)

        copie = self.lots / 'lot_000099'           # même contenu, autre nom
        copie.mkdir(parents=True)
        for nom in ('locations.csv', 'referentiels.json', 'manifest.json', 'READY'):
            (copie / nom).write_bytes((dossier / nom).read_bytes())
        resultat = traitement.traiter_lot(copie, fabrique.lire_manifeste(copie))

        self.assertEqual(resultat['status'], 'DEJA_CHARGE')
        self.assertEqual(self.compter('contracts'), 1)

    def test_nouveau_lot_reutilisant_un_contrat_echoue_sans_rien_ecrire(self):
        dossier, manifeste = self._lot_propre()
        traitement.traiter_lot(dossier, manifeste)
        avant = self.compter('contract_lines')
        avant_journal = len(self.journal('CHARGE'))

        # Contenu différent (durée 5), même contract_id : conflit inter-lots.
        conflit, manifeste_conflit = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000002'),
            [fabrique.ligne(contract_id=100, line_no=1, duration=5)], lot=2)
        with self.assertRaises(depot.ConflitContrat):
            traitement.traiter_lot(conflit, manifeste_conflit)

        self.assertEqual(self.compter('contract_lines'), avant)
        self.assertEqual(len(self.journal('CHARGE')), avant_journal)
        self.assertEqual(self.valeur('SELECT duration FROM contract_lines '
                                     'WHERE contract_id = 100 AND line_no = 1'), 2)

    def test_campagne_differente_refusee(self):
        dossier, manifeste = self._lot_propre()
        traitement.traiter_lot(dossier, manifeste)

        autre, manifeste_autre = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000002'),
            [fabrique.ligne(contract_id=500)], campagne='campagne-test-0002', lot=2)
        resultat = traitement.traiter_lot(autre, manifeste_autre)

        self.assertEqual(resultat['status'], 'REJETE_STRUCTURE')
        self.assertIn('CAMPAGNE_REFUSEE', resultat['motif'])
        self.assertEqual(self.compter('contracts'), 1)

    def test_referentiels_modifies_refuses(self):
        dossier, manifeste = self._lot_propre()
        traitement.traiter_lot(dossier, manifeste)

        modifies = {**fabrique.REFERENTIELS,
                    'clients': fabrique.REFERENTIELS['clients'] +
                    [{'client_id': 11, 'name': 'Association 11'}]}
        autre, manifeste_autre = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000002'),
            [fabrique.ligne(contract_id=501)], referentiels=modifies, lot=2)
        resultat = traitement.traiter_lot(autre, manifeste_autre)
        self.assertEqual(resultat['status'], 'REJETE_STRUCTURE')
        self.assertIn('REFERENTIELS_INCOHERENTS', resultat['motif'])


class TestAlerteQualite(base.BasePipeline):
    def test_taux_superieur_a_20_pourcent_alerte_mais_charge_le_reste(self):
        # 4 contrats sur 10 sont en quarantaine : 40 % de rejet.
        lignes = [fabrique.ligne(contract_id=identifiant) for identifiant in range(1, 7)]
        lignes += [fabrique.ligne(contract_id=identifiant, quantity=-1)
                   for identifiant in range(7, 11)]
        dossier, manifeste = fabrique.ecrire_lot(
            base.dossier_lot(self.lots, 'lot_000001'), lignes, lot=1)
        resultat = traitement.traiter_lot(dossier, manifeste)

        self.assertEqual(resultat['status'], 'CHARGE')
        self.assertEqual(resultat['taux_rejet'], 40.0)
        self.assertTrue(resultat['alerte_qualite'])
        self.assertEqual(resultat['contrats_acceptes'], 6)
        self.assertEqual(self.compter('contracts'), 6)
        self.assertTrue(self.valeur('SELECT alerte_qualite FROM ingestion_batches '
                                    'WHERE status = %s', ('CHARGE',)))


if __name__ == '__main__':
    unittest.main()
