"""Graphiques SVG de la console — rendus côté serveur, animés côté client.

Chaque fonction renvoie un SVG complet. Les animations (tracé, barres, arcs,
apparition) sont pilotées par des classes CSS et la variable `--d` (délai), donc
aucune bibliothèque graphique n’est nécessaire. Les infobulles utilisent
l’attribut `data-tip`, lu par `app.js`.
"""
from __future__ import annotations

import math
from decimal import Decimal

# Palette CampusEquip : contrastes éditoriaux, accents chauds et teal.
CYAN = '#238f89'
VIOLET = '#8977a8'
VERT = '#238f89'
AMBRE = '#e5b84c'
ROSE = '#f07845'
BLEU = '#526d87'
GRIS = '#758173'
TEXTE = '#263449'
TEXTE_DOUX = '#697466'
GRILLE = 'rgba(38,52,73,0.12)'

PALETTE = (CYAN, ROSE, AMBRE, VIOLET, BLEU, '#6d9980', '#bd795d', '#a69a6c')

_compteur = {'n': 0}


def _id(prefixe: str) -> str:
    _compteur['n'] += 1
    return f'{prefixe}{_compteur["n"]}'


def couleur(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def nombre(valeur) -> str:
    if isinstance(valeur, Decimal):
        valeur = float(valeur)
    return f'{valeur:,.0f}'.replace(',', '\u202f')


def _echelle(maximum: float) -> tuple[float, float]:
    maximum = max(float(maximum), 1.0)
    cible = maximum / 4
    base = 10 ** math.floor(math.log10(cible))
    for facteur in (1, 2, 2.5, 5, 10):
        pas = base * facteur
        if pas >= cible:
            return pas, math.ceil(maximum / pas) * pas
    return maximum, maximum


def _grille(dessin: list[str], largeur: int, haut: int, bas: int, gauche: int,
            maximum: float) -> float:
    pas, limite = _echelle(maximum)
    graduations = max(1, int(round(limite / pas)))
    for index in range(graduations + 1):
        valeur = index * pas
        y = bas - (valeur / limite) * (bas - haut)
        dessin.append(f'<line class="grille" x1="{gauche}" y1="{y:.1f}" '
                      f'x2="{largeur - 18}" y2="{y:.1f}"/>')
        dessin.append(f'<text class="axe" x="{gauche - 12}" y="{y + 4:.1f}" '
                      f'text-anchor="end">{nombre(valeur)}</text>')
    return limite


# ---------------------------------------------------------------------------
# Courbe principale
# ---------------------------------------------------------------------------
def aire(jours: list[str], valeurs: list[float], hauteur: int = 300,
         unite: str = 'MAD') -> str:
    largeur, haut, bas, gauche = 1000, 26, hauteur - 30, 66
    identifiant = _id('aire')
    maximum = max(valeurs) if valeurs else 0
    dessin = [f'<svg class="chart" viewBox="0 0 {largeur} {hauteur}" '
              f'preserveAspectRatio="none" role="img" aria-label="Montant retenu par jour">',
              '<defs>',
              f'<linearGradient id="{identifiant}" x1="0" y1="0" x2="0" y2="1">',
              f'<stop offset="0%" stop-color="{CYAN}" stop-opacity="0.34"/>',
              f'<stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>',
              '</linearGradient>',
              '<filter id="lueur" x="-20%" y="-20%" width="140%" height="140%">',
              f'<feGaussianBlur stdDeviation="4" result="flou"/>',
              f'<feMerge><feMergeNode in="flou"/><feMergeNode in="SourceGraphic"/></feMerge>',
              '</filter>',
              '</defs>']
    limite = _grille(dessin, largeur, haut, bas, gauche, maximum)
    pas = (largeur - 18 - gauche) / max(len(jours) - 1, 1)

    points = [(gauche + index * pas, bas - (valeur / limite) * (bas - haut))
              for index, valeur in enumerate(valeurs)]
    if points:
        chemin = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
        dessin.append(f'<polygon class="aire" points="{gauche},{bas} {chemin} '
                      f'{points[-1][0]:.1f},{bas}" fill="url(#{identifiant})"/>')
        dessin.append(f'<polyline class="ligne" pathLength="1" points="{chemin}"/>')
        for index, ((x, y), valeur) in enumerate(zip(points, valeurs)):
            dessin.append(
                f'<circle class="point" cx="{x:.1f}" cy="{y:.1f}" r="3.4" '
                f'style="--d:{0.35 + index * 0.02:.3f}s" '
                f'data-tip="{jours[index]} · <b>{nombre(valeur)} {unite}</b>"/>')
            # Zone de survol large : toute la colonne du jour.
            dessin.append(
                f'<rect class="zone" x="{x - pas / 2:.1f}" y="{haut}" width="{pas:.1f}" '
                f'height="{bas - haut}" data-tip="{jours[index]} · '
                f'<b>{nombre(valeur)} {unite}</b>"/>')

    for index, jour in enumerate(jours):
        if index % 2 == 0 or index == len(jours) - 1:
            dessin.append(f'<text class="axe" x="{gauche + index * pas:.1f}" '
                          f'y="{bas + 20}" text-anchor="middle">{jour}</text>')
    dessin.append(f'<line class="axe-ligne" x1="{gauche}" y1="{bas}" '
                  f'x2="{largeur - 18}" y2="{bas}"/>')
    dessin.append('</svg>')
    return ''.join(dessin)


def etincelle(valeurs: list[float], largeur: int = 132, hauteur: int = 34) -> str:
    """Mini-courbe pour les cartes d’indicateurs."""
    if not valeurs:
        return ''
    maximum = max(valeurs) or 1
    pas = largeur / max(len(valeurs) - 1, 1)
    points = [(index * pas, hauteur - (valeur / maximum) * (hauteur - 4) - 2)
              for index, valeur in enumerate(valeurs)]
    chemin = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
    return (f'<svg class="etincelle" viewBox="0 0 {largeur} {hauteur}" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline pathLength="1" points="{chemin}"/></svg>')


# ---------------------------------------------------------------------------
# Colonnes
# ---------------------------------------------------------------------------
def colonnes(etiquettes: list[str], valeurs: list[float], hauteur: int = 240,
             teinte: str = CYAN) -> str:
    largeur, haut, bas, gauche = 1000, 20, hauteur - 26, 62
    dessin = [f'<svg class="chart" viewBox="0 0 {largeur} {hauteur}" '
              f'preserveAspectRatio="none" role="img" aria-label="Répartition">']
    limite = _grille(dessin, largeur, haut, bas, gauche, max(valeurs or [0]))
    pas = (largeur - 18 - gauche) / max(len(valeurs), 1)
    largeur_barre = max(min(pas * 0.56, 24), 4)
    for index, (etiquette, valeur) in enumerate(zip(etiquettes, valeurs)):
        x = gauche + index * pas + pas / 2
        hauteur_barre = (valeur / limite) * (bas - haut) if limite else 0
        dessin.append(
            f'<rect class="barre" x="{x - largeur_barre / 2:.1f}" '
            f'y="{bas - hauteur_barre:.1f}" width="{largeur_barre:.1f}" '
            f'height="{max(hauteur_barre, 0.8):.1f}" rx="3" fill="{teinte}" '
            f'style="--d:{index * 0.02:.2f}s" data-tip="{etiquette} · '
            f'<b>{nombre(valeur)} MAD</b>"/>')
        if index % 2 == 0 or index == len(valeurs) - 1:
            dessin.append(f'<text class="axe" x="{x:.1f}" y="{bas + 18}" '
                          f'text-anchor="middle">{etiquette}</text>')
    dessin.append(f'<line class="axe-ligne" x1="{gauche}" y1="{bas}" '
                  f'x2="{largeur - 18}" y2="{bas}"/>')
    dessin.append('</svg>')
    return ''.join(dessin)


def barres_horizontales(items: list[tuple[str, float, str]], hauteur_ligne: int = 38) -> str:
    hauteur = max(len(items) * hauteur_ligne + 6, hauteur_ligne)
    largeur, gauche, droite = 520, 176, 90
    maximum = max((valeur for _, valeur, _ in items), default=1) or 1
    dessin = [f'<svg class="chart" viewBox="0 0 {largeur} {hauteur}" role="img" '
              f'aria-label="Classement">']
    for index, (libelle, valeur, teinte) in enumerate(items):
        y = 4 + index * hauteur_ligne
        longueur = (valeur / maximum) * (largeur - gauche - droite)
        dessin.append(f'<text class="axe" x="0" y="{y + 17}" fill="{TEXTE}">{libelle}</text>')
        dessin.append(f'<rect class="piste" x="{gauche}" y="{y + 5}" '
                      f'width="{largeur - gauche - droite}" height="14" rx="7"/>')
        dessin.append(f'<rect class="barre" x="{gauche}" y="{y + 5}" '
                      f'width="{max(longueur, 2):.1f}" height="14" rx="7" fill="{teinte}" '
                      f'style="--d:{index * 0.05:.2f}s" data-tip="{libelle} · '
                      f'<b>{nombre(valeur)} MAD</b>"/>')
        dessin.append(f'<text class="valeur" x="{largeur}" y="{y + 17}" '
                      f'text-anchor="end">{nombre(valeur)}</text>')
    dessin.append('</svg>')
    return ''.join(dessin)


# ---------------------------------------------------------------------------
# Jauge
# ---------------------------------------------------------------------------
def jauge(valeur: float, seuil: float = 20.0, maximum: float = 100.0,
          etiquette: str = 'taux de rejet') -> str:
    rayon, epaisseur = 82, 12
    centre_x, centre_y = 120, 108
    part = min(max(valeur / maximum, 0), 1)

    def point(angle: float, rayon_local: float = rayon) -> tuple[float, float]:
        return (centre_x + rayon_local * math.cos(angle),
                centre_y - rayon_local * math.sin(angle))

    x1, y1 = point(math.pi)
    x2, y2 = point(0.0)
    epaisseur_teinte = ROSE if valeur > seuil else VERT

    angle_seuil = math.pi - math.pi * (seuil / maximum)
    sx, sy = point(angle_seuil, rayon + 11)
    ex, ey = point(angle_seuil, rayon - 11)

    return (f'<svg class="jauge" viewBox="0 0 240 150" role="img" '
            f'aria-label="{etiquette} : {valeur:.1f} pour cent">'
            f'<path class="jauge-fond" d="M {x1:.1f} {y1:.1f} A {rayon} {rayon} 0 0 1 '
            f'{x2:.1f} {y2:.1f}" fill="none" stroke-width="{epaisseur}"/>'
            f'<path class="jauge-arc" d="M {x1:.1f} {y1:.1f} A {rayon} {rayon} 0 0 1 '
            f'{x2:.1f} {y2:.1f}" fill="none" stroke="{epaisseur_teinte}" '
            f'stroke-width="{epaisseur}" pathLength="1" style="--part:{part:.3f}"/>'
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="{TEXTE_DOUX}" stroke-width="1.6" stroke-dasharray="2 3"/>'
            f'<text class="jauge-valeur" x="{centre_x}" y="{centre_y - 6}" '
            f'text-anchor="middle" style="fill:{epaisseur_teinte}">{valeur:.1f}'
            f'<tspan class="jauge-unite"> %</tspan></text>'
            f'<text class="axe" x="{centre_x}" y="{centre_y + 18}" text-anchor="middle">'
            f'{etiquette}</text>'
            f'</svg>')


# ---------------------------------------------------------------------------
# Carte de chaleur campus × jour
# ---------------------------------------------------------------------------
def carte_chaleur(campus: list[dict], jours: list, valeurs: list[list[float]]) -> str:
    if not campus or not jours:
        return ''
    largeur_case, hauteur_case, ecart = 26, 22, 3
    gauche, haut = 128, 30
    largeur = gauche + len(jours) * (largeur_case + ecart) + 8
    hauteur = haut + len(campus) * (hauteur_case + ecart) + 10
    maximum = max((valeur for ligne in valeurs for valeur in ligne), default=1) or 1
    dessin = [f'<svg class="chaleur" viewBox="0 0 {largeur} {hauteur}" role="img" '
              f'aria-label="Montant par campus et par jour">']
    for index, jour in enumerate(jours):
        if index % 3 == 0 or index == len(jours) - 1:
            dessin.append(f'<text class="axe" x="{gauche + index * (largeur_case + ecart) + largeur_case / 2:.1f}" '
                          f'y="18" text-anchor="middle">{jour.strftime("%d")}</text>')
    for ligne, campus_ligne in enumerate(campus):
        y = haut + ligne * (hauteur_case + ecart)
        dessin.append(f'<text class="axe" x="{gauche - 12}" y="{y + 15}" '
                      f'text-anchor="end" fill="{TEXTE}">'
                      f'{campus_ligne["name"].replace("Campus ", "")}</text>')
        for colonne, valeur in enumerate(valeurs[ligne]):
            x = gauche + colonne * (largeur_case + ecart)
            intensite = (valeur / maximum) ** 0.62
            opacite = 0.06 + intensite * 0.94
            dessin.append(
                f'<rect class="case" x="{x}" y="{y}" width="{largeur_case}" '
                f'height="{hauteur_case}" rx="4" fill="{CYAN}" fill-opacity="{opacite:.3f}" '
                f'style="--d:{(ligne * 0.02 + colonne * 0.012):.2f}s" '
                f'data-tip="{campus_ligne["name"]} · {jours[colonne].strftime("%d/%m")} · '
                f'<b>{nombre(valeur)} MAD</b>"/>')
    dessin.append('</svg>')
    return ''.join(dessin)


# ---------------------------------------------------------------------------
# Soleil des catégories (bonus récursif)
# ---------------------------------------------------------------------------
def soleil(racines: list[dict]) -> str:
    total = sum(racine['montant'] for racine in racines) or 1
    rayon_interieur, rayon_exterieur = 58, 84
    rayon_enfant_interieur, rayon_enfant_exterieur = 90, 118
    dessin = ['<svg class="soleil" viewBox="0 0 280 280" role="img" '
              'aria-label="Montants par catégorie et sous-catégorie">',
              '<circle cx="140" cy="140" r="128" class="soleil-fond"/>']
    angle = -math.pi / 2

    def arc(centre: float, rayon: float, debut: float, fin: float) -> str:
        x1 = 140 + rayon * math.cos(debut)
        y1 = 140 + rayon * math.sin(debut)
        x2 = 140 + rayon * math.cos(fin)
        y2 = 140 + rayon * math.sin(fin)
        grand = 1 if (fin - debut) > math.pi else 0
        return (f'M {x1:.2f} {y1:.2f} A {rayon} {rayon} 0 {grand} 1 {x2:.2f} {y2:.2f} '
                f'L {140 + centre * math.cos(fin):.2f} {140 + centre * math.sin(fin):.2f} '
                f'A {centre} {centre} 0 {grand} 0 '
                f'{140 + centre * math.cos(debut):.2f} {140 + centre * math.sin(debut):.2f} Z')

    for index, racine in enumerate(racines):
        part = racine['montant'] / total
        fin = angle + part * 2 * math.pi
        ecart = 0.012 if part > 0.02 else 0.004
        couleur_racine = couleur(index)
        dessin.append(
            f'<path class="segment" d="{arc(rayon_interieur, rayon_exterieur, angle + ecart, fin - ecart)}" '
            f'fill="{couleur_racine}" fill-opacity="0.9" '
            f'data-tip="{racine["nom"]} · <b>{nombre(racine["montant"])} MAD</b> · '
            f'{part * 100:.1f} %"/>')
        if racine['enfants']:
            sous_angle = angle
            for enfant in racine['enfants']:
                sous_part = enfant['montant'] / total
                sous_fin = sous_angle + sous_part * 2 * math.pi
                if sous_fin - sous_angle > 0.004:
                    chemin = arc(rayon_enfant_interieur, rayon_enfant_exterieur,
                                 sous_angle + 0.006, sous_fin - 0.006)
                    dessin.append(
                        f'<path class="segment" d="{chemin}" '
                        f'fill="{couleur_racine}" fill-opacity="0.42" '
                        f'data-tip="{racine["nom"]} › {enfant["nom"]} · '
                        f'<b>{nombre(enfant["montant"])} MAD</b>"/>')
                sous_angle = sous_fin
        angle = fin

    dessin.append(f'<text class="soleil-total" x="140" y="136" text-anchor="middle">'
                  f'{nombre(total)}</text>'
                  f'<text class="axe" x="140" y="156" text-anchor="middle">MAD</text>')
    dessin.append('</svg>')
    return ''.join(dessin)


# ---------------------------------------------------------------------------
# Frise du pipeline
# ---------------------------------------------------------------------------
def frise(etapes: list[dict]) -> str:
    largeur = 1000
    hauteur = 132
    nombre_etapes = len(etapes)
    pas = largeur / nombre_etapes
    dessin = [f'<svg class="frise" viewBox="0 0 {largeur} {hauteur}" role="img" '
              f'aria-label="Étapes du pipeline">']
    for index, etape in enumerate(etapes):
        x = pas * index + pas / 2
        if index < nombre_etapes - 1:
            dessin.append(f'<line class="flux" x1="{x + 26}" y1="46" '
                          f'x2="{x + pas - 26}" y2="46"/>')
        ton = etape.get('ton', CYAN)
        dessin.append(
            f'<circle class="noeud" cx="{x}" cy="46" r="13" '
            f'style="--d:{index * 0.12:.2f}s; --ton:{ton}"/>')
        dessin.append(f'<text class="frise-valeur" x="{x}" y="51" text-anchor="middle">'
                      f'{etape["valeur"]}</text>')
        dessin.append(f'<text class="frise-label" x="{x}" y="84" text-anchor="middle">'
                      f'{etape["titre"]}</text>')
        dessin.append(f'<text class="axe" x="{x}" y="102" text-anchor="middle">'
                      f'{etape["detail"]}</text>')
    dessin.append('</svg>')
    return ''.join(dessin)


# ---------------------------------------------------------------------------
# Nuage IoT
# ---------------------------------------------------------------------------
def nuage_iot(points: list[dict]) -> str:
    """Carte des boîtiers : chaque position observée devient une bulle, la taille
    reflétant le nombre d’observations (les points isolés se chevaucheraient)."""
    if not points:
        return ('<div class="vide-mini">Aucune observation : '
                'lancez <code>python -m outils.preuve_iot</code></div>')

    groupes: dict[tuple, dict] = {}
    for point in points:
        cle = (round(float(point['latitude']), 2), round(float(point['longitude']), 2))
        groupe = groupes.setdefault(cle, {'lat': cle[0], 'lon': cle[1], 'n': 0,
                                          'boitiers': set(), 'equipements': set()})
        groupe['n'] += 1
        groupe['boitiers'].add(point['device_id'])
        groupe['equipements'].add(point['equipment_id'])

    latitudes = [groupe['lat'] for groupe in groupes.values()]
    longitudes = [groupe['lon'] for groupe in groupes.values()]
    marge = 0.02
    lat_min, lat_max = min(latitudes) - marge, max(latitudes) + marge
    lon_min, lon_max = min(longitudes) - marge, max(longitudes) + marge
    lat_span = max(lat_max - lat_min, 0.02)
    lon_span = max(lon_max - lon_min, 0.02)
    largeur, hauteur = 520, 320

    def x(longitude):
        return 34 + (longitude - lon_min) / lon_span * (largeur - 68)

    def y(latitude):
        return hauteur - 34 - (latitude - lat_min) / lat_span * (hauteur - 68)

    maximum = max(groupe['n'] for groupe in groupes.values())
    dessin = [f'<svg class="nuage" viewBox="0 0 {largeur} {hauteur}" role="img" '
              f'aria-label="Positions des boîtiers GPS simulés">']
    for index in range(1, 4):
        dessin.append(f'<line class="grille" x1="34" y1="{34 + index * 63}" '
                      f'x2="{largeur - 34}" y2="{34 + index * 63}"/>')
        dessin.append(f'<line class="grille" x1="{34 + index * 113}" y1="34" '
                      f'x2="{34 + index * 113}" y2="{hauteur - 34}"/>')
    for index, groupe in enumerate(sorted(groupes.values(), key=lambda g: -g['n'])):
        rayon = 7 + (groupe['n'] / maximum) ** 0.5 * 22
        teinte = CYAN if groupe['n'] < maximum else VIOLET
        cx, cy = x(groupe['lon']), y(groupe['lat'])
        dessin.append(f'<circle class="halo" cx="{cx:.1f}" cy="{cy:.1f}" '
                      f'r="{rayon * 1.6:.1f}" fill="{teinte}" '
                      f'style="--d:{index * 0.15:.2f}s"/>')
        dessin.append(
            f'<circle class="capteur" cx="{cx:.1f}" cy="{cy:.1f}" r="{rayon:.1f}" '
            f'fill="{teinte}" style="--d:{index * 0.15:.2f}s" '
            f'data-tip="{groupe["n"]} observation(s) · {len(groupe["boitiers"])} boîtier(s) · '
            f'{len(groupe["equipements"])} équipement(s)"/>')
        if groupe['n'] >= 3:
            dessin.append(f'<text class="nuage-valeur" x="{cx:.1f}" y="{cy + 4:.1f}" '
                          f'text-anchor="middle">{groupe["n"]}</text>')
    dessin.append(f'<text class="axe" x="{largeur - 30}" y="{hauteur - 12}" '
                  f'text-anchor="end">longitude →</text>')
    dessin.append(f'<text class="axe" x="12" y="30" transform="rotate(-90 12 30)" '
                  f'text-anchor="end">latitude</text>')
    dessin.append('</svg>')
    return ''.join(dessin)
