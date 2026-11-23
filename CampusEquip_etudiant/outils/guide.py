"""Génère le guide du projet en Markdown, DOCX et PDF.

    python -m outils.guide

Le contenu vient de `outils/guide_contenu.py`. Le DOCX est converti en PDF par
LibreOffice s'il est installé ; sinon le DOCX reste produit et l'absence de
conversion est signalée.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from outils.guide_contenu import contenu  # noqa: E402


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def rendre_markdown(blocs: list[tuple]) -> str:
    sortie: list[str] = []
    for bloc in blocs:
        genre = bloc[0]
        if genre == 'couverture':
            sortie += [f'# {bloc[1]}', '', f'## {bloc[2]}', '']
            for libelle, valeur in bloc[3]:
                sortie.append(f'**{libelle}** · {valeur}  ')
            sortie += ['', '---', '']
        elif genre == 'h1':
            sortie += [f'## {bloc[1]}', '']
        elif genre == 'h2':
            sortie += [f'### {bloc[1]}', '']
        elif genre == 'h3':
            sortie += [f'#### {bloc[1]}', '']
        elif genre == 'p':
            sortie += [bloc[1], '']
        elif genre == 'ul':
            sortie += [f'- {element}' for element in bloc[1]] + ['']
        elif genre == 'ol':
            sortie += [f'{index}. {element}' for index, element in enumerate(bloc[1], 1)] + ['']
        elif genre == 'code':
            sortie += ['```text', bloc[1], '```', '']
        elif genre == 'table':
            entetes, lignes = bloc[1], bloc[2]
            sortie.append('| ' + ' | '.join(entetes) + ' |')
            sortie.append('|' + '|'.join('---' for _ in entetes) + '|')
            for ligne in lignes:
                sortie.append('| ' + ' | '.join(str(valeur) for valeur in ligne) + ' |')
            sortie.append('')
        elif genre == 'note':
            sortie += [f'> **{bloc[1]}**', '>', f'> {bloc[2]}', '']
        elif genre == 'image':
            sortie += [f'![{bloc[3]}]({bloc[1]})', '', f'*{bloc[3]}*', '']
        elif genre == 'saut':
            sortie += ['---', '']
    return '\n'.join(sortie)


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------
def rendre_docx(blocs: list[tuple], chemin: Path) -> Path:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
    from docx.shared import Cm, Pt, RGBColor

    NAVY = RGBColor(0x1D, 0x4E, 0x89)
    ENCRE = RGBColor(0x10, 0x18, 0x28)
    GRIS = RGBColor(0x55, 0x5F, 0x6D)

    document = Document()
    section = document.sections[0]
    section.page_height, section.page_width = Cm(29.7), Cm(21)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.9)
    section.left_margin = Cm(2.1)
    section.right_margin = Cm(2.1)

    normal = document.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.08

    def entete_pied():
        entete = section.header.paragraphs[0]
        entete.text = 'CampusEquip — guide du projet'
        entete.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in entete.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = GRIS

        pied = section.footer.paragraphs[0]
        pied.alignment = WD_ALIGN_PARAGRAPH.CENTER
        premier = pied.add_run('— ')
        premier.font.size = Pt(8)
        premier.font.color.rgb = GRIS

        run = pied.add_run()
        debut = OxmlElement('w:fldChar')
        debut.set(qn('w:fldCharType'), 'begin')
        instruction = OxmlElement('w:instrText')
        instruction.set(qn('xml:space'), 'preserve')
        instruction.text = ' PAGE '
        fin = OxmlElement('w:fldChar')
        fin.set(qn('w:fldCharType'), 'end')
        run._r.append(debut)
        run._r.append(instruction)
        run._r.append(fin)
        run.font.size = Pt(8)
        run.font.color.rgb = GRIS

        dernier = pied.add_run(' —')
        dernier.font.size = Pt(8)
        dernier.font.color.rgb = GRIS

    def ombre_paragraphe(paragraphe, couleur: str, bordure: bool = False):
        proprietes = paragraphe._p.get_or_add_pPr()
        proprietes.append(parse_xml(r'<w:shd {} w:val="clear" w:fill="{}"/>'
                                    .format(nsdecls('w'), couleur)))
        if bordure:
            proprietes.append(parse_xml(
                r'<w:pBdr {}><w:left w:val="single" w:sz="18" w:space="8" '
                r'w:color="1D4E89"/></w:pBdr>'.format(nsdecls('w'))))

    def bordures(table, couleur: str = 'E4E7EC'):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table_pr = table._tbl.tblPr
        bordures_xml = (f'<w:tblBorders {nsdecls("w")}>'
                        + ''.join(f'<w:{cote} w:val="single" w:sz="4" w:space="0" '
                                  f'w:color="{couleur}"/>'
                                  for cote in ('top', 'left', 'bottom', 'right',
                                               'insideH', 'insideV'))
                        + '</w:tblBorders>')
        table_pr.append(parse_xml(bordures_xml))

    def fond_cellule(cellule, couleur: str):
        cellule._tc.get_or_add_tcPr().append(
            parse_xml(r'<w:shd {} w:val="clear" w:fill="{}"/>'.format(nsdecls('w'), couleur)))

    entete_pied()

    premiere = True
    for bloc in blocs:
        genre = bloc[0]

        if genre == 'couverture':
            document.add_paragraph()
            logo = RACINE / 'docs' / 'captures' / 'mark.png'
            if logo.is_file():
                document.add_picture(str(logo), width=Cm(2.0))
            document.add_paragraph()
            titre = document.add_paragraph()
            run = titre.add_run(bloc[1])
            run.bold = True
            run.font.size = Pt(40)
            run.font.color.rgb = NAVY
            titre.paragraph_format.space_after = Pt(2)

            sous_titre = document.add_paragraph()
            run = sous_titre.add_run(bloc[2])
            run.font.size = Pt(16)
            run.font.color.rgb = ENCRE
            sous_titre.paragraph_format.space_after = Pt(24)

            table = document.add_table(rows=0, cols=2)
            bordures(table)
            for libelle, valeur in bloc[3]:
                cellules = table.add_row().cells
                cellules[0].width = Cm(4.2)
                cellules[1].width = Cm(12.5)
                paragraphe = cellules[0].paragraphs[0]
                run = paragraphe.add_run(libelle.upper())
                run.bold = True
                run.font.size = Pt(8)
                run.font.color.rgb = GRIS
                fond_cellule(cellules[0], 'F8FAFC')
                paragraphe2 = cellules[1].paragraphs[0]
                run = paragraphe2.add_run(valeur)
                run.font.size = Pt(10)

            document.add_paragraph()
            note = document.add_paragraph()
            run = note.add_run(
                'Document de travail — il accompagne le code et le rapport. '
                'Les chiffres cités proviennent de la base de démonstration livrée.')
            run.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = GRIS
            document.add_page_break()
            premiere = True          # la page suivante est déjà ouverte
            continue

        if genre == 'h1':
            paragraphe = document.add_paragraph()
            run = paragraphe.add_run(bloc[1])
            run.bold = True
            run.font.size = Pt(19)
            run.font.color.rgb = NAVY
            paragraphe.paragraph_format.space_before = Pt(0 if premiere else 26)
            paragraphe.paragraph_format.space_after = Pt(10)
            paragraphe.paragraph_format.keep_with_next = True
            premiere = False
            ombre_paragraphe(paragraphe, 'FFFFFF', bordure=True)
        elif genre == 'h2':
            paragraphe = document.add_paragraph()
            run = paragraphe.add_run(bloc[1])
            run.bold = True
            run.font.size = Pt(12.5)
            run.font.color.rgb = ENCRE
            paragraphe.paragraph_format.space_before = Pt(10)
            paragraphe.paragraph_format.space_after = Pt(4)
        elif genre == 'h3':
            paragraphe = document.add_paragraph()
            run = paragraphe.add_run(bloc[1])
            run.bold = True
            run.font.size = Pt(11)
            paragraphe.paragraph_format.space_before = Pt(6)
        elif genre == 'p':
            paragraphe = document.add_paragraph()
            question = bloc[1].startswith('Q. ')
            run = paragraphe.add_run(bloc[1])
            run.font.size = Pt(10)
            if question:
                run.bold = True
                run.font.color.rgb = NAVY
                paragraphe.paragraph_format.space_before = Pt(6)
                paragraphe.paragraph_format.space_after = Pt(1)
            paragraphe.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        elif genre == 'ul':
            for element in bloc[1]:
                paragraphe = document.add_paragraph(style='List Bullet')
                run = paragraphe.add_run(element)
                run.font.size = Pt(9.5)
                paragraphe.paragraph_format.space_after = Pt(2)
        elif genre == 'ol':
            for index, element in enumerate(bloc[1], 1):
                paragraphe = document.add_paragraph(style='List Number')
                run = paragraphe.add_run(element)
                run.font.size = Pt(9.5)
                paragraphe.paragraph_format.space_after = Pt(2)
        elif genre == 'code':
            paragraphe = document.add_paragraph()
            for numero, ligne in enumerate(bloc[1].splitlines()):
                run = paragraphe.add_run(ligne)
                run.font.name = 'Consolas'
                run.font.size = Pt(8.5)
                if numero < len(bloc[1].splitlines()) - 1:
                    run.add_break(WD_BREAK.LINE)
            paragraphe.paragraph_format.left_indent = Cm(0.35)
            paragraphe.paragraph_format.space_before = Pt(2)
            paragraphe.paragraph_format.space_after = Pt(8)
            paragraphe.paragraph_format.line_spacing = 1.0
            ombre_paragraphe(paragraphe, 'F6F8FA')
        elif genre == 'table':
            entetes, lignes = bloc[1], bloc[2]
            largeurs = bloc[3] if len(bloc) > 3 else None
            table = document.add_table(rows=1, cols=len(entetes))
            bordures(table)
            if largeurs:
                table.autofit = False
                for index, largeur in enumerate(largeurs):
                    table.columns[index].width = Cm(largeur)
            table.rows[0]._tr.get_or_add_trPr().append(
                parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
            for index, entete in enumerate(entetes):
                cellule = table.rows[0].cells[index]
                if largeurs:
                    cellule.width = Cm(largeurs[index])
                fond_cellule(cellule, '1D4E89')
                paragraphe = cellule.paragraphs[0]
                run = paragraphe.add_run(entete)
                run.bold = True
                run.font.size = Pt(8.5)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            for numero, ligne in enumerate(lignes):
                cellules = table.add_row().cells
                for index, valeur in enumerate(ligne):
                    if largeurs:
                        cellules[index].width = Cm(largeurs[index])
                    paragraphe = cellules[index].paragraphs[0]
                    run = paragraphe.add_run(str(valeur))
                    run.font.size = Pt(8.5)
                    paragraphe.paragraph_format.space_after = Pt(1)
                    if numero % 2 == 1:
                        fond_cellule(cellules[index], 'FAFBFC')
            document.add_paragraph()
        elif genre == 'note':
            table = document.add_table(rows=1, cols=1)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table._tbl.tblPr.append(parse_xml(
                f'<w:tblBorders {nsdecls("w")}><w:left w:val="single" w:sz="18" w:space="0" '
                f'w:color="1D4E89"/><w:top w:val="nil"/><w:bottom w:val="nil"/>'
                f'<w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/>'
                f'</w:tblBorders>'))
            cellule = table.rows[0].cells[0]
            fond_cellule(cellule, 'F8FAFC')
            paragraphe = cellule.paragraphs[0]
            run = paragraphe.add_run(bloc[1])
            run.bold = True
            run.font.size = Pt(9)
            run.font.color.rgb = NAVY
            for ligne in bloc[2].split('\n'):
                paragraphe = cellule.add_paragraph()
                run = paragraphe.add_run(ligne)
                run.font.size = Pt(9)
                paragraphe.paragraph_format.space_after = Pt(2)
            document.add_paragraph()
        elif genre == 'image':
            chemin_image = RACINE / bloc[1]
            if chemin_image.is_file():
                document.add_picture(str(chemin_image), width=Cm(bloc[2]))
                if bloc[3]:
                    legende = document.add_paragraph()
                    run = legende.add_run(bloc[3])
                    run.italic = True
                    run.font.size = Pt(8.5)
                    run.font.color.rgb = GRIS
                    legende.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif genre == 'saut':
            document.add_page_break()

    document.save(str(chemin))
    return chemin


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def convertir_pdf(docx: Path) -> Path | None:
    libreoffice = shutil.which('libreoffice') or shutil.which('soffice')
    if libreoffice is None:
        print('LibreOffice indisponible : le PDF n’a pas été régénéré.')
        return None
    pdf = docx.with_suffix('.pdf')
    if pdf.exists():
        pdf.unlink()
    resultat = subprocess.run(
        [libreoffice, '--headless', '--convert-to', 'pdf', '--outdir',
         str(docx.parent), str(docx)],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    if resultat.returncode != 0 or not pdf.is_file():
        print('Conversion PDF impossible :', (resultat.stderr or resultat.stdout)[-400:])
        return None
    print('PDF :', pdf.name, f'({pdf.stat().st_size // 1024} Ko)')
    return pdf


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--sans-pdf', action='store_true')
    arguments = p.parse_args()

    blocs = contenu()
    markdown = RACINE / 'GUIDE_PROJET.md'
    markdown.write_text(rendre_markdown(blocs), encoding='utf-8')
    print('Markdown :', markdown.name)

    docx = rendre_docx(blocs, RACINE / 'GUIDE_PROJET.docx')
    print('DOCX :', docx.name, f'({docx.stat().st_size // 1024} Ko)')

    if not arguments.sans_pdf:
        convertir_pdf(docx)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
