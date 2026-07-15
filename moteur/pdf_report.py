# -*- coding: utf-8 -*-
"""Export PDF du rapport décisionnel (inspiré de pdf_generator.py de l'équipe AirEka) :
page de couverture, KPIs colorés, tableaux des secteurs, métiers et répartition géographique.
"""
import io
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

PRIMARY = colors.HexColor("#1F5C3F")
ACCENT = colors.HexColor("#E8792C")
LIGHT = colors.HexColor("#EAF2EE")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ACPETitle", fontSize=26, leading=30, alignment=TA_CENTER,
                               textColor=PRIMARY, spaceAfter=6, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="ACPESubtitle", fontSize=13, alignment=TA_CENTER,
                               textColor=colors.HexColor("#444444"), spaceAfter=24))
    styles.add(ParagraphStyle(name="ACPESection", fontSize=15, textColor=PRIMARY,
                               spaceBefore=18, spaceAfter=10, fontName="Helvetica-Bold"))
    return styles


def _kpi_table(pairs):
    t = Table([[k, v] for k, v in pairs], colWidths=[9 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("TEXTCOLOR", (1, 0), (1, -1), PRIMARY),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    return t


def _dict_table(d, headers, max_rows=10):
    rows = [headers] + [[k, str(v)] for k, v in list(d.items())[:max_rows]]
    t = Table(rows, colWidths=[10 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def generate_report(stats):
    """Génère le PDF en mémoire et retourne les bytes (pour st.download_button)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = _styles()
    story = []

    # --- Page de couverture ---
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("ACPE Matcher", styles["ACPETitle"]))
    story.append(Paragraph("Rapport décisionnel — Console Conseiller", styles["ACPESubtitle"]))
    story.append(Paragraph(
        f"Généré le {datetime.date.today().strftime('%d/%m/%Y')} — "
        f"Agence Congolaise pour l'Emploi (ACPE) · Hackathon IndabaX Congo 2026",
        ParagraphStyle(name="cover_date", alignment=TA_CENTER, fontSize=10,
                       textColor=colors.HexColor("#777777"))
    ))
    story.append(PageBreak())

    # --- KPIs ---
    story.append(Paragraph("Indicateurs clés", styles["ACPESection"]))
    kpi_pairs = [
        ("Candidats actifs", f"{stats['n_candidats']:,}".replace(",", " ")),
        ("Offres d'emploi", f"{stats['n_offres']:,}".replace(",", " ")),
        ("Offres à texte riche", stats["n_offres_texte_riche"]),
        ("Taux moyen de compatibilité (Top-1)", f"{stats['taux_moyen_compatibilite_top1']*100:.1f} %"),
    ]
    story.append(_kpi_table(kpi_pairs))
    story.append(Spacer(1, 0.8 * cm))

    # --- Secteurs ---
    story.append(Paragraph("Secteurs les plus représentés (offres)", styles["ACPESection"]))
    story.append(_dict_table(stats["secteurs_offres_top10"], ["Secteur", "Nombre d'offres"]))
    story.append(Spacer(1, 0.6 * cm))

    story.append(Paragraph("Métiers les plus demandés (candidats)", styles["ACPESection"]))
    story.append(_dict_table(stats["metiers_demandes_top10"], ["Métier visé", "Nombre de candidats"]))
    story.append(PageBreak())

    # --- Répartition géographique ---
    story.append(Paragraph("Répartition géographique (départements)", styles["ACPESection"]))
    story.append(_dict_table(stats["repartition_candidats_par_departement"],
                              ["Département", "Candidats"], max_rows=15))
    story.append(Spacer(1, 0.6 * cm))
    story.append(_dict_table(stats["repartition_offres_par_departement"],
                              ["Département", "Offres"], max_rows=15))

    doc.build(story)
    buf.seek(0)
    return buf.read()
