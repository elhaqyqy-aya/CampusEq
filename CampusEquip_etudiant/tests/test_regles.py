"""Tests des règles pures : parseurs, dédoublonnage, cohérence, signature.

Ces tests ne demandent pas PostgreSQL : ils prouvent que la décision ne dépend
pas de la base, et que la base ne corrige pas une valeur refusée.
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from etudiant import regles
from tests import fabrique


class TestParseurs(unittest.TestCase):
    def test_entier_positif_accepte_les_espaces_peripheriques(self):
        self.assertEqual(regles.entier_positif(' 12 '), 12)
        self.assertEqual(regles.entier_positif('0007'), 7)

    def test_entier_positif_refuse_tout_le_reste(self):
        for valeur in ('', ' ', '0', '-1', '+1', '1.0', '1 2', 'abc', '12,0', '99999999999'):
            with self.subTest(valeur=valeur):
                with self.assertRaises(regles.ValeurInvalide):
                    regles.entier_positif(valeur)

    def test_tarif_deux_decimales_maximum(self):
        self.assertEqual(regles.tarif('25.00'), Decimal('25.00'))
        self.assertEqual(regles.tarif(' 25.5 '), Decimal('25.5'))
        self.assertEqual(regles.tarif('0'), Decimal('0'))
        self.assertEqual(regles.tarif('0.00'), Decimal('0.00'))

    def test_tarif_refuse_ce_qui_changerait_le_sens(self):
        for valeur in ('25.555', '1,5', '-1', '1e3', 'NaN', 'Infinity', '', '5.', '.5'):
            with self.subTest(valeur=valeur):
                with self.assertRaises(regles.ValeurInvalide):
                    regles.tarif(valeur)

    def test_date_iso_stricte(self):
        self.assertEqual(regles.date_iso('2026-11-02').isoformat(), '2026-11-02')
        for valeur in ('2026-02-30', '02/11/2026', '2026-11-2', '20261102', ''):
            with self.subTest(valeur=valeur):
                with self.assertRaises(regles.ValeurInvalide):
                    regles.date_iso(valeur)

    def test_duree_depend_de_l_unite(self):
        self.assertEqual(regles.duree('720', 'hour'), 720)
        self.assertEqual(regles.duree('365', 'day'), 365)
        for valeur, unite in (('721', 'hour'), ('366', 'day'), ('0', 'day')):
            with self.subTest(valeur=valeur, unite=unite):
                with self.assertRaises(regles.ValeurInvalide):
                    regles.duree(valeur, unite)

    def test_normalisation_limitee(self):
        ligne = regles.normaliser_ligne({'contract_id': ' 7 ', 'status': ' PAID ',
                                         'unit': ' HOUR ', 'unit_rate': ' 12.50 '})
        self.assertEqual(ligne['contract_id'], '7')
        self.assertEqual(ligne['status'], 'paid')
        self.assertEqual(ligne['unit'], 'hour')
        self.assertEqual(ligne['unit_rate'], '12.50')
        # Aucune autre réparation : la virgule du tarif reste refusée plus loin.
        self.assertEqual(regles.normaliser_ligne({'unit_rate': '12,50'})['unit_rate'], '12,50')


class TestReferentiels(unittest.TestCase):
    def test_empreinte_independante_de_l_ordre_des_cles(self):
        premier = regles.Referentiels.depuis_json(fabrique.REFERENTIELS)
        reordonne = {cle: fabrique.REFERENTIELS[cle]
                     for cle in reversed(list(fabrique.REFERENTIELS))}
        second = regles.Referentiels.depuis_json(reordonne)
        self.assertEqual(premier.empreinte(), second.empreinte())

    def test_referentiel_incoherent_refuse(self):
        casse = {**fabrique.REFERENTIELS,
                 'equipment': [{'equipment_id': 1, 'name': 'X', 'category_id': 99}]}
        with self.assertRaises(regles.StructureInvalide):
            regles.Referentiels.depuis_json(casse)


class TestAnalyseLot(unittest.TestCase):
    def setUp(self):
        self.referentiels = regles.Referentiels.depuis_json(fabrique.REFERENTIELS)

    def analyser(self, lignes):
        return regles.analyser_lot(fabrique.COLONNES, lignes, self.referentiels)

    def test_montant_heure_et_journee(self):
        analyse = self.analyser([
            fabrique.ligne(contract_id=2001, line_no=1, unit='hour', quantity=2,
                           duration=3, unit_rate='25.00'),
            fabrique.ligne(contract_id=2001, line_no=2, unit='day', quantity=1,
                           duration=2, unit_rate='200.00'),
        ])
        self.assertEqual([ligne.montant for ligne in analyse.lignes],
                         [Decimal('150.00'), Decimal('400.00')])
        self.assertEqual(sum(ligne.montant for ligne in analyse.acceptees), Decimal('550.00'))

    def test_repetition_exacte_comptee_une_fois(self):
        ligne = fabrique.ligne(contract_id=1)
        analyse = self.analyser([ligne, dict(ligne)])
        self.assertEqual(len(analyse.doublons), 1)
        self.assertEqual(analyse.lignes_apres_dedoublonnage, 1)
        self.assertEqual(len(analyse.acceptees), 1)

    def test_cle_de_ligne_en_conflit_isole_tout_le_contrat(self):
        analyse = self.analyser([
            fabrique.ligne(contract_id=2, line_no=1, duration=2),
            fabrique.ligne(contract_id=2, line_no=1, duration=3),
            fabrique.ligne(contract_id=2, line_no=2, duration=4),
        ])
        self.assertEqual(len(analyse.rejetees), 3)
        self.assertTrue(all('CLE_LIGNE_EN_CONFLIT' in motif
                            for ligne in analyse.rejetees for motif in ligne.motifs))

    def test_quantite_invalide_et_quantite_25(self):
        analyse = self.analyser([
            fabrique.ligne(contract_id=3, quantity=-1),
            fabrique.ligne(contract_id=4, quantity=25),
        ])
        rejetee = [ligne for ligne in analyse.lignes if ligne.contrat_cle == '3'][0]
        acceptee = [ligne for ligne in analyse.lignes if ligne.contrat_cle == '4'][0]
        self.assertFalse(rejetee.acceptee)
        self.assertTrue(acceptee.acceptee)
        self.assertEqual(len(acceptee.anomalies), 1)
        self.assertIn('QUANTITE_ELEVEE', acceptee.anomalies[0])

    def test_entete_de_contrat_contradictoire(self):
        analyse = self.analyser([
            fabrique.ligne(contract_id=5, line_no=1, status='paid'),
            fabrique.ligne(contract_id=5, line_no=2, status='closed'),
        ])
        self.assertEqual(len(analyse.rejetees), 2)
        self.assertTrue(any('ENTETE_CONTRAT_CONTRADICTOIRE' in motif
                            for ligne in analyse.rejetees for motif in ligne.motifs))

    def test_reference_inconnue_met_le_contrat_en_quarantaine(self):
        analyse = self.analyser([
            fabrique.ligne(contract_id=6, line_no=1, client_id=999),
            fabrique.ligne(contract_id=6, line_no=2, client_id=999),
        ])
        self.assertEqual(len(analyse.rejetees), 2)
        self.assertTrue(all(any('CLIENT_INCONNU' in motif for motif in ligne.motifs)
                            for ligne in analyse.rejetees))

    def test_taux_de_rejet_apres_dedoublonnage(self):
        self.assertEqual(regles.taux_rejet(10, 17), Decimal('58.82'))
        self.assertEqual(regles.taux_rejet(0, 0), Decimal('0.00'))
        self.assertEqual(regles.taux_rejet(0, 5), Decimal('0.00'))

    def test_ligne_mal_formee_ne_casse_pas_l_analyse(self):
        analyse = self.analyser([
            fabrique.ligne(contract_id=7),
            ['7', 'trop', 'peu'],
        ])
        # La ligne mal formée isole tout son contrat : les deux lignes sortent.
        self.assertEqual(len(analyse.rejetees), 2)
        self.assertTrue(any('COLONNES_INCOHERENTES' in motif
                            for ligne in analyse.rejetees for motif in ligne.motifs))


class TestSignature(unittest.TestCase):
    def setUp(self):
        self.a = 'a' * 64
        self.b = 'b' * 64

    def test_signature_stable(self):
        une = regles.signature_lot(self.a, self.b)
        autre = regles.signature_lot(self.a, self.b)
        self.assertEqual(une, autre)
        self.assertRegex(une, r'^[0-9a-f]{64}$')

    def test_signature_depend_du_contenu_et_des_regles(self):
        reference = regles.signature_lot(self.a, self.b)
        self.assertNotEqual(reference, regles.signature_lot(self.b, self.a))
        self.assertNotEqual(reference, regles.signature_lot(self.a, self.b, 'regles-v9'))
        self.assertNotEqual(reference, regles.signature_lot(self.a, 'c' * 64))

    def test_signature_refuse_une_empreinte_invalide(self):
        with self.assertRaises(regles.StructureInvalide):
            regles.signature_lot('pas-un-sha', self.b)


if __name__ == '__main__':
    unittest.main()
