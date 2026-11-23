"""Graphiques du projet, dessinés avec Pillow (aucune dépendance lourde).

Deux figures suffisent au sujet :
  * `courbes_journalieres` : montant par jour et par campus (analyse A1) ;
  * `barres_unites`       : heure / journée par campus (analyse A3).

Les images sont écrites en PNG, lisibles telles quelles et insérables dans le
rapport. Les couleurs restent distinguables en niveaux de gris.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COULEURS = ['#1f4e79', '#c0504d', '#2e7d32', '#8a6d1f', '#6a3d9a', '#00838f',
            '#b35900', '#455a64']

POLICES = ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/segoeui.ttf',
           'C:/Windows/Fonts/calibri.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
POLICES_GRAS = ('C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/segoeuib.ttf',
                'C:/Windows/Fonts/calibrib.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')


def _police(taille: int, gras: bool = False):
    for chemin in (POLICES_GRAS if gras else POLICES):
        if Path(chemin).is_file():
            try:
                return ImageFont.truetype(chemin, taille)
            except OSError:                      # pragma: no cover - police illisible
                continue
    return ImageFont.load_default()


def montant_lisible(valeur: float) -> str:
    """Format français lisible : 12 345 MAD."""
    entier = f'{valeur:,.0f}'.replace(',', ' ')
    return f'{entier} MAD'


def _echelle(maximum: float) -> tuple[float, float]:
    """Choisit un pas et une borne « ronds » pour environ 4 à 5 graduations."""
    maximum = max(float(maximum), 1.0)
    base = 10 ** (len(str(int(maximum))) - 2)
    for facteur in (1, 2, 2.5, 5, 10):
        pas = base * facteur
        if maximum / pas <= 5:
            return pas, -(-maximum // pas) * pas
    return maximum, maximum


def _axe_y(dessin, zone, maximum, largeur_gauche, police):
    """Trace la grille et les graduations verticales ; renvoie l'échelle."""
    gauche, haut, droite, bas = zone
    pas, limite = _echelle(maximum)
    graduations = 1 if pas <= 0 else int(round(limite / pas))
    for index in range(graduations + 1):
        multiple = index * pas
        y = bas - (multiple / limite) * (bas - haut)
        dessin.line([(gauche, y), (droite, y)], fill='#d9d9d9', width=1)
        dessin.text((largeur_gauche - 16, y), montant_lisible(multiple), font=police,
                    fill='#444444', anchor='rm')
    return limite


def courbes_journalieres(jours: list[str], series: dict[str, list[float]], chemin,
                         titre: str, sous_titre: str = '') -> Path:
    """Courbes d'évolution : une ligne par campus, une graduation par jour."""
    chemin = Path(chemin)
    largeur, hauteur = 1600, 900
    gauche, haut, droite, bas = 170, 160, 1120, 780
    image = Image.new('RGB', (largeur, hauteur), 'white')
    dessin = ImageDraw.Draw(image)
    police_titre = _police(38, gras=True)
    police_sous = _police(23)
    police_axe = _police(22)
    police_legende = _police(23)
    police_valeur = _police(19, gras=True)

    dessin.text((gauche, 40), titre, font=police_titre, fill='#111111')
    if sous_titre:
        dessin.text((gauche, 94), sous_titre, font=police_sous, fill='#555555')

    maximum = max((max(valeurs) if valeurs else 0) for valeurs in series.values())
    limite = _axe_y(dessin, (gauche, haut, droite, bas), maximum, gauche, police_axe)

    pas_x = (droite - gauche) / (len(jours) - 1) if len(jours) > 1 else 0
    for index, jour in enumerate(jours):
        x = gauche + index * pas_x
        dessin.line([(x, bas), (x, bas + 6)], fill='#666666', width=2)
        # Une graduation sur deux garde les étiquettes lisibles sur 21 jours.
        if index % 2 == 0 or index == len(jours) - 1:
            dessin.text((x, bas + 14), jour, font=police_axe, fill='#333333', anchor='ma')

    dessin.line([(gauche, bas), (droite, bas)], fill='#333333', width=2)
    dessin.line([(gauche, haut), (gauche, bas)], fill='#333333', width=2)

    for index, (nom, valeurs) in enumerate(series.items()):
        couleur = COULEURS[index % len(COULEURS)]
        points = [(gauche + position * pas_x,
                   bas - (valeur / limite) * (bas - haut))
                  for position, valeur in enumerate(valeurs)]
        if len(points) > 1:
            dessin.line(points, fill=couleur, width=4, joint='curve')
        for x, y in points:
            dessin.ellipse([x - 4, y - 4, x + 4, y + 4], fill=couleur)

        # Légende à droite, avec le total de la période.
        y_legende = haut + 14 + index * 46
        dessin.line([(droite + 44, y_legende), (droite + 88, y_legende)], fill=couleur, width=6)
        dessin.text((droite + 98, y_legende), nom, font=police_legende, fill='#222222',
                    anchor='lm')
        dessin.text((droite + 98, y_legende + 23), montant_lisible(sum(valeurs)),
                    font=police_valeur, fill='#777777', anchor='lm')

    image.save(chemin, format='PNG', optimize=True)
    return chemin


def barres_unites(campus: list[str], heures: list[float], journees: list[float], chemin,
                  titre: str) -> Path:
    """Barres groupées : montant heure vs montant journée, par campus."""
    chemin = Path(chemin)
    largeur, hauteur = 1500, 850
    gauche, haut, droite, bas = 170, 160, 1420, 750
    image = Image.new('RGB', (largeur, hauteur), 'white')
    dessin = ImageDraw.Draw(image)
    police_titre = _police(36, gras=True)
    police_axe = _police(22)
    police_etiquette = _police(17, gras=True)
    police_legende = _police(24)

    dessin.text((gauche, 52), titre, font=police_titre, fill='#111111')
    dessin.text((gauche, 100), 'montants en MAD — contrats payés et clôturés',
                font=_police(21), fill='#555555')
    maximum = max(max(heures, default=0), max(journees, default=0), 1)
    limite = _axe_y(dessin, (gauche, haut, droite, bas), maximum, gauche, police_axe)

    nombre = max(len(campus), 1)
    largeur_groupe = (droite - gauche) / nombre
    largeur_barre = largeur_groupe * 0.28
    for index, nom in enumerate(campus):
        centre = gauche + largeur_groupe * (index + 0.5)
        for decalage, (valeur, couleur) in enumerate(
                ((heures[index], COULEURS[0]), (journees[index], COULEURS[1]))):
            x = centre + (decalage - 0.5) * (largeur_barre + 8)
            hauteur_barre = (valeur / limite) * (bas - haut)
            dessin.rectangle([x - largeur_barre / 2, bas - hauteur_barre,
                              x + largeur_barre / 2, bas], fill=couleur)
            dessin.text((x, bas - hauteur_barre - 8), f'{valeur:,.0f}'.replace(',', ' '),
                        font=police_etiquette, fill='#333333', anchor='mb')
        dessin.text((centre, bas + 16), nom, font=police_axe, fill='#333333', anchor='ma')

    dessin.line([(gauche, bas), (droite, bas)], fill='#333333', width=2)
    dessin.line([(gauche, haut), (gauche, bas)], fill='#333333', width=2)

    for index, (nom, couleur) in enumerate((("à l'heure", COULEURS[0]),
                                            ('à la journée', COULEURS[1]))):
        x = 1080 + index * 175
        dessin.rectangle([x, 116, x + 24, 138], fill=couleur)
        dessin.text((x + 32, 127), nom, font=police_legende, fill='#222222', anchor='lm')

    image.save(chemin, format='PNG', optimize=True)
    return chemin
