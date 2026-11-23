"""Règles métier de CampusEquip — fonctions pures, sans PostgreSQL.

Ce module contient tout ce qui décide du sort d'une ligne : normalisation,
dédoublonnage, contrôles de valeur, cohérence d'un contrat, calcul du montant.
Il ne lit aucun fichier et n'écrit rien : les tests peuvent donc l'exercer
directement, et `etudiant/traitement.py` se contente de l'orchestrer.

Conventions du sujet :
  * seules les valeurs reçues sont conservées, aucune valeur n'est inventée ;
  * les espaces périphériques sont retirés, `status` et `unit` passent en
    minuscules ; aucune autre réparation n'est autorisée ;
  * une ligne invalide met TOUT son contrat en quarantaine ;
  * `quantity > 20` n'est pas un rejet, c'est une anomalie signalée ;
  * le taux de rejet se calcule APRÈS dédoublonnage.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

RULES_VERSION = 'campusequip-v2.0'
SCHEMA_VERSION = 'campusequip-v2'

COLONNES = (
    'contract_id', 'client_id', 'site_id', 'start_date', 'status',
    'line_no', 'equipment_id', 'quantity', 'unit', 'duration', 'unit_rate',
)

STATUTS = ('paid', 'closed', 'draft', 'cancelled')
STATUTS_RETENUS = ('paid', 'closed')          # seuls ces statuts comptent
UNITES = ('hour', 'day')
DUREE_MAX = {'hour': 720, 'day': 365}

QUANTITE_MIN = 1
QUANTITE_MAX = 100
QUANTITE_SIGNALEMENT = 20                     # au-delà : anomalie, pas rejet
ENTIER_MAX = 2_147_483_647                    # borne des colonnes integer
TAUX_MAX = Decimal('9999999999.99')           # borne de numeric(12,2)
TAUX_REJET_ALERTE = Decimal('20')             # pourcentage

_RE_ENTIER = re.compile(r'\A[0-9]+\Z')
_RE_TAUX = re.compile(r'\A[0-9]+(?:\.[0-9]{1,2})?\Z')
_RE_DATE = re.compile(r'\A[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')


class ValeurInvalide(ValueError):
    """Une valeur ne respecte pas la règle annoncée (message destiné au rapport)."""


class StructureInvalide(ValueError):
    """Un lot ne peut pas être interprété : rejet avant toute écriture métier."""


# ---------------------------------------------------------------------------
# 1. Parseurs : conversion stricte, jamais d'arrondi silencieux
# ---------------------------------------------------------------------------
def normaliser(valeur) -> str:
    """Retourne la valeur texte sans espaces périphériques."""
    if valeur is None:
        return ''
    return str(valeur).strip()


def normaliser_ligne(champs: dict) -> dict:
    """Copie normalisée d'une ligne : strip partout, minuscules ciblées."""
    ligne = {colonne: normaliser(champs.get(colonne, '')) for colonne in COLONNES}
    ligne['status'] = ligne['status'].lower()
    ligne['unit'] = ligne['unit'].lower()
    return ligne


def entier_positif(valeur, maximum: int = ENTIER_MAX) -> int:
    """Chiffres uniquement, valeur strictement positive, plafonnée."""
    texte = normaliser(valeur)
    if not texte:
        raise ValeurInvalide('valeur absente')
    if not _RE_ENTIER.match(texte):
        raise ValeurInvalide(f"« {texte} » n'est pas un entier (chiffres uniquement)")
    nombre = int(texte)
    if nombre <= 0:
        raise ValeurInvalide(f'« {texte} » doit être strictement positif')
    if nombre > maximum:
        raise ValeurInvalide(f'« {texte} » dépasse le maximum {maximum}')
    return nombre


def tarif(valeur) -> Decimal:
    """Tarif en MAD : point décimal, au plus 2 décimales, positif ou nul, fini."""
    texte = normaliser(valeur)
    if not texte:
        raise ValeurInvalide('tarif absent')
    if ',' in texte:
        raise ValeurInvalide(f'« {texte} » : la virgule décimale est refusée, utilisez un point')
    if not _RE_TAUX.match(texte):
        raise ValeurInvalide(f'« {texte} » : format attendu 12 ou 12.34 (2 décimales maximum)')
    try:
        montant = Decimal(texte)
    except InvalidOperation:                     # pragma: no cover - défense
        raise ValeurInvalide(f'« {texte} » n\'est pas un nombre décimal') from None
    if not montant.is_finite():                  # pragma: no cover - défense
        raise ValeurInvalide(f'« {texte} » n\'est pas un nombre fini')
    if montant < 0:
        raise ValeurInvalide(f'« {texte} » est négatif')
    if montant > TAUX_MAX:
        raise ValeurInvalide(f'« {texte} » dépasse le tarif maximal {TAUX_MAX}')
    return montant


def date_iso(valeur) -> date:
    """Date au format exact YYYY-MM-DD et existante dans le calendrier."""
    texte = normaliser(valeur)
    if not _RE_DATE.match(texte):
        raise ValeurInvalide(f'« {texte} » : format attendu YYYY-MM-DD')
    try:
        return date.fromisoformat(texte)
    except ValueError:
        raise ValeurInvalide(f'« {texte} » n\'existe pas dans le calendrier') from None


def statut(valeur) -> str:
    texte = normaliser(valeur).lower()
    if texte not in STATUTS:
        raise ValeurInvalide(f'« {texte} » : statut attendu parmi {", ".join(STATUTS)}')
    return texte


def unite(valeur) -> str:
    texte = normaliser(valeur).lower()
    if texte not in UNITES:
        raise ValeurInvalide(f'« {texte} » : unité attendue hour ou day')
    return texte


def quantite(valeur) -> int:
    nombre = entier_positif(valeur, QUANTITE_MAX)
    if nombre < QUANTITE_MIN:                    # pragma: no cover - entier_positif
        raise ValeurInvalide('quantité nulle')
    return nombre


def duree(valeur, unite_ligne: str) -> int:
    maximum = DUREE_MAX[unite_ligne]
    return entier_positif(valeur, maximum)


# ---------------------------------------------------------------------------
# 2. Référentiels
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Referentiels:
    """Contenu de referentiels.json, validé structurellement et conservé tel quel."""

    campuses: dict[int, str]
    sites: dict[int, tuple[int, str]]        # site_id -> (campus_id, name)
    clients: dict[int, str]                  # client_id -> name
    categories: dict[int, tuple[str, int | None]]
    equipments: dict[int, tuple[int, str]]   # equipment_id -> (category_id, name)

    # -- construction ------------------------------------------------------
    @classmethod
    def depuis_json(cls, document) -> 'Referentiels':
        if not isinstance(document, dict):
            raise StructureInvalide('referentiels.json doit être un objet JSON')
        for cle in ('campuses', 'sites', 'clients', 'categories', 'equipment'):
            if not isinstance(document.get(cle), list):
                raise StructureInvalide(f'référentiel « {cle} » absent ou non tabulaire')

        campuses = {campus_id: str(champs['name']).strip()
                    for campus_id, champs in _indexer(
                        document['campuses'], 'campus', 'campus_id', ('name',)).items()}
        sites_bruts = _indexer(document['sites'], 'site', 'site_id', ('name', 'campus_id'))
        clients_bruts = _indexer(document['clients'], 'client', 'client_id', ('name',))
        categories_brutes = _indexer(
            document['categories'], 'catégorie', 'category_id', ('name',), optionnels=('parent_id',))
        equipements_bruts = _indexer(
            document['equipment'], 'équipement', 'equipment_id', ('name', 'category_id'))

        sites = {}
        for site_id, champs in sites_bruts.items():
            campus_id = _entier_reference(champs.get('campus_id'), f'campus_id du site {site_id}')
            if campus_id not in campuses:
                raise StructureInvalide(f'le site {site_id} référence le campus inconnu {campus_id}')
            sites[site_id] = (campus_id, str(champs['name']).strip())

        clients = {client_id: str(champs['name']).strip()
                   for client_id, champs in clients_bruts.items()}

        categories = {}
        for category_id, champs in categories_brutes.items():
            parent = champs.get('parent_id')
            if parent in (None, ''):
                parent_id = None
            else:
                parent_id = _entier_reference(parent, f'parent_id de la catégorie {category_id}')
            categories[category_id] = (str(champs['name']).strip(), parent_id)
        for category_id, (_, parent_id) in categories.items():
            if parent_id is not None and parent_id not in categories:
                raise StructureInvalide(
                    f'la catégorie {category_id} référence le parent inconnu {parent_id}')

        equipments = {}
        for equipment_id, champs in equipements_bruts.items():
            category_id = _entier_reference(champs.get('category_id'),
                                            f'category_id de l\'équipement {equipment_id}')
            if category_id not in categories:
                raise StructureInvalide(
                    f"l'équipement {equipment_id} référence la catégorie inconnue {category_id}")
            equipments[equipment_id] = (category_id, str(champs['name']).strip())

        return cls(campuses=campuses, sites=sites, clients=clients,
                   categories=categories, equipments=equipments)

    # -- usage -------------------------------------------------------------
    def site_connu(self, site_id: int) -> bool:
        return site_id in self.sites

    def client_connu(self, client_id: int) -> bool:
        return client_id in self.clients

    def equipement_connu(self, equipment_id: int) -> bool:
        return equipment_id in self.equipments

    def empreinte(self) -> str:
        """Empreinte canonique : deux référentiels équivalents ont la même valeur.

        Le simple SHA-256 du fichier changerait avec l'indentation ; cette
        empreinte ne dépend que du contenu métier, et c'est elle que la base
        compare pour vérifier que les référentiels d'une campagne sont fixes.
        """
        canonique = {
            'campuses': sorted([campus_id, nom] for campus_id, nom in self.campuses.items()),
            'sites': sorted([site_id, campus_id, nom]
                            for site_id, (campus_id, nom) in self.sites.items()),
            'clients': sorted([client_id, nom] for client_id, nom in self.clients.items()),
            'categories': sorted([category_id, nom, parent_id]
                                 for category_id, (nom, parent_id) in self.categories.items()),
            'equipment': sorted([equipment_id, category_id, nom]
                                for equipment_id, (category_id, nom) in self.equipments.items()),
        }
        texte = json.dumps(canonique, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(texte.encode('utf-8')).hexdigest()


def _indexer(liste, libelle, cle, champs_requis, optionnels=()) -> dict[int, dict]:
    index = {}
    for element in liste:
        if not isinstance(element, dict) or cle not in element:
            raise StructureInvalide(f'{libelle} mal formé : {element!r}')
        identifiant = _entier_reference(element[cle], f'{cle} d\'un {libelle}')
        if identifiant in index:
            raise StructureInvalide(f'{libelle} {identifiant} présent deux fois')
        for champ in champs_requis:
            if element.get(champ) is None:
                raise StructureInvalide(f'{libelle} {identifiant} : champ « {champ} » absent')
        index[identifiant] = element
    if not index:
        raise StructureInvalide(f'aucun {libelle} dans le référentiel')
    return index


def _entier_reference(valeur, libelle) -> int:
    try:
        return entier_positif(valeur)
    except ValeurInvalide as erreur:
        raise StructureInvalide(f'{libelle} invalide : {erreur}') from None


# ---------------------------------------------------------------------------
# 3. Lignes et analyse d'un lot
# ---------------------------------------------------------------------------
@dataclass
class Ligne:
    """Une ligne source et sa décision. `brut` reste intact pour la preuve."""

    position: int                       # numéro de ligne physique dans le CSV
    champs: dict | None                 # valeurs brutes (dict) si 11 colonnes
    brut: list | None = None            # valeurs brutes (liste) sinon
    norm: dict | None = None
    contrat_cle: str | None = None      # contract_id normalisé, même illisible
    valeurs: dict | None = None         # valeurs typées après contrôle
    montant: Decimal | None = None
    motifs: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    @property
    def acceptee(self) -> bool:
        return not self.motifs

    def valeurs_brutes_json(self) -> dict:
        if self.champs is not None:
            return dict(self.champs)
        return {'colonnes_recues': list(self.brut or [])}


@dataclass
class AnalyseLot:
    lignes: list[Ligne]                 # lignes uniques après dédoublonnage
    doublons: list[Ligne]               # répétitions exactes retirées
    lignes_recues: int
    contrats_recus: int
    contrats_acceptes: int
    contrats_rejetes: int

    @property
    def acceptees(self) -> list[Ligne]:
        return [ligne for ligne in self.lignes if ligne.acceptee]

    @property
    def rejetees(self) -> list[Ligne]:
        return [ligne for ligne in self.lignes if not ligne.acceptee]

    @property
    def anomalies(self) -> list[Ligne]:
        return [ligne for ligne in self.lignes if ligne.anomalies and ligne.acceptee]

    @property
    def contrats_acceptes_ids(self) -> list[int]:
        return sorted({ligne.valeurs['contract_id'] for ligne in self.acceptees})

    @property
    def lignes_apres_dedoublonnage(self) -> int:
        return len(self.lignes)

    @property
    def taux_rejet(self) -> Decimal:
        return taux_rejet(len(self.rejetees), len(self.lignes))

    @property
    def alerte(self) -> bool:
        return self.taux_rejet > TAUX_REJET_ALERTE


def dedupliquer(lignes: list[Ligne]) -> tuple[list[Ligne], list[Ligne]]:
    """Retire les répétitions EXACTES après normalisation.

    La clé est la ligne entière (11 colonnes normalisées), pas `contract_id` :
    deux lignes d'un même contrat ne sont pas des copies.
    """
    vues: set[tuple] = set()
    uniques, doublons = [], []
    for ligne in lignes:
        cle = cle_dedoublonnage(ligne.norm)
        if cle in vues:
            doublons.append(ligne)
            continue
        vues.add(cle)
        uniques.append(ligne)
    return uniques, doublons


def controler_ligne(norm: dict, referentiels: Referentiels) -> tuple[dict, list[str], list[str]]:
    """Contrôle une ligne normalisée.

    Renvoie (valeurs typées, motifs de rejet, anomalies). Une valeur typée n'est
    produite que si la colonne est valide ; le montant n'est calculé que si
    toute la ligne est valide.
    """
    valeurs: dict = {}
    motifs: list[str] = []
    anomalies: list[str] = []

    def essayer(colonne, fonction, *arguments, prefixe=''):
        try:
            valeurs[colonne] = fonction(norm[colonne], *arguments)
        except ValeurInvalide as erreur:
            motifs.append(f'{prefixe}{colonne.upper()}_INVALIDE: {erreur}')

    essayer('contract_id', entier_positif)
    essayer('client_id', entier_positif)
    essayer('site_id', entier_positif)
    essayer('start_date', date_iso)
    essayer('status', statut)
    essayer('line_no', entier_positif)
    essayer('equipment_id', entier_positif)
    essayer('quantity', quantite)

    # L'unité conditionne la borne de durée : on la résout d'abord.
    try:
        valeurs['unit'] = unite(norm['unit'])
    except ValeurInvalide as erreur:
        motifs.append(f'UNIT_INVALIDE: {erreur}')
    if 'unit' in valeurs:
        essayer('duration', duree, valeurs['unit'])
    essayer('unit_rate', tarif)
    # Références : elles ne valident pas la ligne, elles la font rejeter.
    if 'client_id' in valeurs and not referentiels.client_connu(valeurs['client_id']):
        motifs.append(f"CLIENT_INCONNU: client_id {valeurs['client_id']} absent du référentiel")
    if 'site_id' in valeurs and not referentiels.site_connu(valeurs['site_id']):
        motifs.append(f"SITE_INCONNU: site_id {valeurs['site_id']} absent du référentiel")
    if 'equipment_id' in valeurs and not referentiels.equipement_connu(valeurs['equipment_id']):
        motifs.append(
            f"EQUIPEMENT_INCONNU: equipment_id {valeurs['equipment_id']} absent du référentiel")

    if 'quantity' in valeurs and valeurs['quantity'] > QUANTITE_SIGNALEMENT:
        anomalies.append(
            f'QUANTITE_ELEVEE: quantité {valeurs["quantity"]} supérieure à {QUANTITE_SIGNALEMENT}')

    return valeurs, motifs, anomalies


def _cle_contrat(norm: dict | None, champs: list | None) -> str | None:
    """Identifiant normalisé du contrat, même si sa valeur est illisible."""
    if norm is not None:
        return norm['contract_id']
    if champs:
        return str(champs[0]).strip()
    return None


def cle_dedoublonnage(norm: dict) -> tuple:
    """Clé d'une répétition exacte : la ligne entière, pas le contrat."""
    return tuple(norm[colonne] for colonne in COLONNES)


def construire_ligne(position: int, champs, referentiels: Referentiels) -> Ligne:
    """Construit une ligne contrôlée à partir d'une ligne source.

    C'est la seule fabrique de `Ligne` : la lecture complète et la lecture par
    morceaux l'utilisent toutes les deux, donc leurs décisions ne peuvent pas
    diverger.
    """
    if isinstance(champs, dict):
        if tuple(champs) != COLONNES:
            raise StructureInvalide('ligne dictionnaire incomplète')
        brut_liste = [champs[colonne] for colonne in COLONNES]
        contenu = dict(champs)
    else:
        brut_liste = list(champs)
        contenu = dict(zip(COLONNES, brut_liste)) if len(brut_liste) == len(COLONNES) else None

    ligne = Ligne(position=position, champs=contenu, brut=brut_liste)
    if contenu is None:
        ligne.motifs.append(
            f'COLONNES_INCOHERENTES: {len(brut_liste)} colonnes reçues au lieu de {len(COLONNES)}')
        ligne.contrat_cle = _cle_contrat(None, brut_liste)
    else:
        ligne.norm = normaliser_ligne(contenu)
        ligne.contrat_cle = _cle_contrat(ligne.norm, None)
        ligne.valeurs, ligne.motifs, ligne.anomalies = controler_ligne(ligne.norm, referentiels)
    return ligne


def analyser_lot(entetes: list[str], lignes_brutes: list[list[str] | dict],
                 referentiels: Referentiels) -> AnalyseLot:
    """Applique toutes les décisions du sujet à un lot déjà lu.

    `entetes` doit être exactement COLONNES : la vérification est faite ici pour
    que le module reste utilisable seul dans les tests.
    """
    if tuple(entetes) != COLONNES:
        raise StructureInvalide(
            f'en-tête inattendu : {list(entetes)} ; attendu {list(COLONNES)}')

    lignes = [construire_ligne(position, champs, referentiels)
              for position, champs in enumerate(lignes_brutes, start=2)]
    uniques, doublons = dedupliquer([ligne for ligne in lignes if ligne.norm is not None])
    malformees = [ligne for ligne in lignes if ligne.norm is None]
    return finaliser_analyse(uniques, malformees, doublons, len(lignes))


def finaliser_analyse(uniques: list[Ligne], malformees: list[Ligne],
                      doublons: list[Ligne], lignes_recues: int) -> AnalyseLot:
    """Décisions qui demandent TOUT le lot : cohérence des contrats puis montants.

    Cette étape est séparée pour que la lecture par morceaux l'appelle une seule
    fois à la fin : un contrat à cheval sur deux morceaux n'est jamais coupé.
    """
    groupes: dict[str, list[Ligne]] = {}
    for ligne in uniques + malformees:
        groupes.setdefault(ligne.contrat_cle or f'?{ligne.position}', []).append(ligne)

    for cle, lignes_contrat in groupes.items():
        motifs_contrat = _controler_contrat(lignes_contrat)
        # Une seule ligne invalide suffit : tout le contrat part en quarantaine.
        causes = [(ligne.position, ligne.motifs[0].split(':', 1)[0])
                  for ligne in lignes_contrat if ligne.motifs]
        if not motifs_contrat and not causes:
            continue
        for ligne in lignes_contrat:
            if ligne.motifs:
                continue                     # la ligne fautive garde son motif propre
            if motifs_contrat:
                ligne.motifs.extend(motifs_contrat)
            else:
                ligne.motifs.append(
                    f'CONTRAT_EN_QUARANTAINE: ligne {causes[0][0]} invalide '
                    f'({causes[0][1]}), tout le contrat est isolé')

    # Montant des lignes réellement acceptées : Decimal, jamais de float.
    for ligne in uniques + malformees:
        if ligne.acceptee:
            ligne.montant = calculer_montant(ligne.valeurs)

    contrats_acceptes = sum(1 for membres in groupes.values() if all(m.acceptee for m in membres))
    contrats_rejetes = len(groupes) - contrats_acceptes

    analyse = AnalyseLot(
        lignes=sorted(uniques + malformees, key=lambda l: l.position),
        doublons=doublons,
        lignes_recues=lignes_recues,
        contrats_recus=len(groupes),
        contrats_acceptes=contrats_acceptes,
        contrats_rejetes=contrats_rejetes,
    )
    assert len(analyse.lignes) == len(analyse.acceptees) + len(analyse.rejetees)
    return analyse


def _controler_contrat(lignes_contrat: list[Ligne]) -> list[str]:
    """Motifs qui mettent tout le contrat en quarantaine."""
    motifs: list[str] = []

    lignes_completes = [ligne for ligne in lignes_contrat if ligne.norm is not None]
    entetes = {(ligne.valeurs.get('client_id'), ligne.valeurs.get('site_id'),
                ligne.valeurs.get('start_date'), ligne.valeurs.get('status'))
               for ligne in lignes_completes
               if set(('client_id', 'site_id', 'start_date', 'status')) <= set(ligne.valeurs)}
    if len(entetes) > 1:
        motifs.append(
            'ENTETE_CONTRAT_CONTRADICTOIRE: client_id, site_id, start_date ou status '
            'diffèrent entre les lignes du contrat')

    # Même clé (contract_id, line_no) avec un contenu différent après
    # dédoublonnage : le contrat est ambigu, toutes ses lignes sont isolées.
    contenus: dict[str, set[tuple]] = {}
    for ligne in lignes_completes:
        cle = ligne.norm['line_no']
        contenus.setdefault(cle, set()).add(tuple(ligne.norm[c] for c in COLONNES))
    if any(len(valeurs) > 1 for valeurs in contenus.values()):
        motifs.append(
            'CLE_LIGNE_EN_CONFLIT: même (contract_id, line_no) avec un contenu différent')

    return motifs


def calculer_montant(valeurs: dict) -> Decimal:
    """Montant de la ligne : quantité x durée x tarif, en Decimal."""
    return (Decimal(valeurs['quantity']) * Decimal(valeurs['duration'])
            * valeurs['unit_rate']).quantize(Decimal('0.01'))


def taux_rejet(rejetees: int, apres_dedoublonnage: int) -> Decimal:
    """Taux de rejet en pourcentage, arrondi à 2 décimales ; 0 si dénominateur nul."""
    if apres_dedoublonnage <= 0:
        return Decimal('0.00')
    return (Decimal(rejetees) * Decimal(100) / Decimal(apres_dedoublonnage)) \
        .quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# 4. Signature d'un lot
# ---------------------------------------------------------------------------
def signature_lot(locations_sha256: str, referentiels_sha256: str,
                  rules_version: str = RULES_VERSION) -> str:
    """Signature stable d'un lot : contenu des deux sources + version des règles.

    Le nom du dossier et le nom des fichiers n'entrent pas dans la signature :
    un lot redéposé sous un autre nom est reconnu comme déjà traité.
    """
    for empreinte in (locations_sha256, referentiels_sha256):
        if not isinstance(empreinte, str) or not re.fullmatch(r'[0-9a-f]{64}', empreinte):
            raise StructureInvalide(f'empreinte SHA-256 invalide : {empreinte!r}')
    matiere = f'{rules_version}|{locations_sha256}|{referentiels_sha256}'
    return hashlib.sha256(matiere.encode('utf-8')).hexdigest()
