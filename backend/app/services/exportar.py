"""
Generación de reportes Excel (.xlsx) y PDF, en el backend, a partir de columnas
+ filas ya consultadas (con los filtros aplicados por el caller).

Excel = formato de trabajo (todas las columnas, encabezado con formato + panel
congelado + autofiltro, formatos numéricos/fecha reales, colores de situación).
PDF = formato para imprimir/compartir (horizontal, encabezado institucional,
resumen, "Página X de Y", fila de encabezado repetida por página).
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

# Colores (hex sin '#') — replican los de la UI para que el doc reconozca su Excel.
SITUACION_COLORES = {
    "DESABASTECIDO": "842029",
    "CRITICO": "DC3545",
    "SUBSTOCK": "FFC107",
    "NORMOSTOCK": "198754",
    "SOBRESTOCK": "0D6EFD",
    "SIN ROTACION": "6C757D",
}
ESTADO_VENC_COLORES = {"VENCIDO": "DC3545", "PROXIMO_A_VENCER": "FD7E14"}
_TEXTO_NEGRO = {"SUBSTOCK"}  # relleno claro → texto negro
_ROJO = "DC3545"
CABECERA_BG = "212529"

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MEDIA = "application/pdf"


@dataclass
class Columna:
    clave: str
    titulo: str
    tipo: str = "texto"  # texto | entero | decimal | fecha
    colores: dict[str, str] | None = None  # valor → hex (colorea la celda)
    resaltar_negativo: bool = False  # números < 0 en rojo


# ── Utilidades de formato ─────────────────────────────────────────────────

def _a_fecha(v):
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def _num_es(v, decimales: int) -> str:
    try:
        d = Decimal(str(v))
    except Exception:
        return str(v)
    s = f"{d:,.{decimales}f}"  # 1,234.56
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _texto_celda(v, col: Columna) -> str:
    if v is None or v == "":
        return ""
    if col.tipo == "entero":
        return _num_es(v, 0)
    if col.tipo == "decimal":
        return _num_es(v, 2)
    if col.tipo == "fecha":
        f = _a_fecha(v)
        return f.strftime("%d/%m/%Y") if f else ""
    return str(v)


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t or "reporte"


def nombre_archivo(modulo: str, partes: list[str], extension: str) -> str:
    hoy = datetime.now().strftime("%Y%m%d")
    trozos = [slug(modulo)] + [slug(p) for p in partes if p] + [hoy]
    return "_".join(trozos) + "." + extension


# ── Excel ─────────────────────────────────────────────────────────────────

def generar_excel(
    titulo: str,
    meta: list[tuple[str, str]],
    columnas: list[Columna],
    filas: list[dict],
    grupos: list[tuple[str, int]] | None = None,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"

    r = 1
    ws.cell(r, 1, titulo).font = Font(bold=True, size=14)
    r += 1
    for etiqueta, valor in meta:
        celda = ws.cell(r, 1, f"{etiqueta}: {valor}")
        celda.font = Font(bold=False, size=10, color="555555")
        r += 1
    ws.cell(r, 1, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}").font = Font(size=10, color="555555")
    r += 1  # línea en blanco

    # Fila de encabezados de GRUPO (como la fila 2 del Excel del doc).
    if grupos:
        col = 1
        for titulo_g, span in grupos:
            if span <= 0:
                continue
            ini = get_column_letter(col)
            fin = get_column_letter(col + span - 1)
            ws.merge_cells(f"{ini}{r}:{fin}{r}")
            c = ws.cell(r, col, titulo_g)
            c.fill = PatternFill("solid", fgColor="343a40")
            c.font = Font(bold=True, color="FFFFFF")
            c.alignment = Alignment(horizontal="center", vertical="center")
            col += span
        r += 1

    fila_header = r
    header_fill = PatternFill("solid", fgColor=CABECERA_BG)
    header_font = Font(bold=True, color="FFFFFF")
    for j, col in enumerate(columnas, start=1):
        c = ws.cell(fila_header, j, col.titulo)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, fila in enumerate(filas):
        rr = fila_header + 1 + i
        for j, col in enumerate(columnas, start=1):
            v = fila.get(col.clave)
            c = ws.cell(rr, j)
            if v is None or v == "":
                c.value = None
            elif col.tipo == "entero":
                c.value = float(v)
                c.number_format = "#,##0"
            elif col.tipo == "decimal":
                c.value = float(v)
                c.number_format = "#,##0.00"
            elif col.tipo == "fecha":
                f = _a_fecha(v)
                if f:
                    c.value = f
                    c.number_format = "DD/MM/YYYY"
            else:
                c.value = str(v)

            if col.colores and isinstance(v, str) and v in col.colores:
                c.fill = PatternFill("solid", fgColor=col.colores[v])
                c.font = Font(bold=True, color="000000" if v in _TEXTO_NEGRO else "FFFFFF")
                c.alignment = Alignment(horizontal="center")
            elif col.resaltar_negativo and isinstance(v, (int, float, Decimal)) and float(v) < 0:
                c.font = Font(bold=True, color=_ROJO)

    ws.freeze_panes = ws.cell(fila_header + 1, 1)
    ultima = get_column_letter(len(columnas))
    ws.auto_filter.ref = f"A{fila_header}:{ultima}{fila_header + len(filas)}"

    for j, col in enumerate(columnas, start=1):
        ancho = len(col.titulo)
        for fila in filas:
            ancho = max(ancho, len(_texto_celda(fila.get(col.clave), col)))
        ws.column_dimensions[get_column_letter(j)].width = min(55, max(8, ancho + 2))

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PDF ───────────────────────────────────────────────────────────────────

class _LienzoNumerado(canvas.Canvas):
    """Pie con 'Página X de Y' (dos pasadas para conocer el total)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._guardadas = []

    def showPage(self):
        self._guardadas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._guardadas)
        for estado in self._guardadas:
            self.__dict__.update(estado)
            self._pie(total)
            super().showPage()
        super().save()

    def _pie(self, total: int):
        ancho = self._pagesize[0]
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.grey)
        self.drawString(12 * mm, 8 * mm, "Red de Salud Coronel Portillo · Sistema de Gestión de Medicamentos")
        self.drawRightString(ancho - 12 * mm, 8 * mm, f"Página {self._pageNumber} de {total}")


def generar_pdf(
    titulo: str,
    meta: list[tuple[str, str]],
    columnas: list[Columna],
    filas: list[dict],
    resumen: list[str] | None = None,
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=titulo,
    )
    estilos = getSampleStyleSheet()
    est_titulo = ParagraphStyle("t", parent=estilos["Title"], fontSize=14, spaceAfter=2)
    est_inst = ParagraphStyle("i", parent=estilos["Normal"], fontSize=9, textColor=colors.HexColor("#495057"))
    est_meta = ParagraphStyle("m", parent=estilos["Normal"], fontSize=8, textColor=colors.HexColor("#555555"))

    story = [
        Paragraph("Red de Salud Coronel Portillo", est_inst),
        Paragraph(titulo, est_titulo),
    ]
    for etiqueta, valor in meta:
        story.append(Paragraph(f"<b>{etiqueta}:</b> {valor}", est_meta))
    story.append(Paragraph(f"<b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", est_meta))
    story.append(Spacer(1, 4 * mm))

    if resumen:
        story.append(Paragraph("<b>Resumen</b>", est_meta))
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(resumen), est_meta))
        story.append(Spacer(1, 3 * mm))

    # Anchos proporcionales al contenido (muestreado), escalados al ancho útil.
    usable = landscape(A4)[0] - 24 * mm
    pesos = []
    for col in columnas:
        m = len(col.titulo)
        for fila in filas[:300]:
            m = max(m, len(_texto_celda(fila.get(col.clave), col)))
        pesos.append(min(m, 42))
    suma = sum(pesos) or 1
    col_widths = [usable * p / suma for p in pesos]

    est_celda = ParagraphStyle("c", parent=estilos["Normal"], fontSize=7, leading=8)
    encabezado = [Paragraph(f"<b>{c.titulo}</b>", ParagraphStyle("h", parent=est_celda, textColor=colors.white)) for c in columnas]
    data = [encabezado]
    for fila in filas:
        data.append([Paragraph(_texto_celda(fila.get(c.clave), c), est_celda) for c in columnas])

    tabla = LongTable(data, colWidths=col_widths, repeatRows=1)
    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#" + CABECERA_BG)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7f9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ])
    # Colores de situación/estado como fondo de celda.
    for i, fila in enumerate(filas, start=1):
        for j, col in enumerate(columnas):
            v = fila.get(col.clave)
            if col.colores and isinstance(v, str) and v in col.colores:
                estilo.add("BACKGROUND", (j, i), (j, i), HexColor("#" + col.colores[v]))
                estilo.add("TEXTCOLOR", (j, i), (j, i), colors.black if v in _TEXTO_NEGRO else colors.white)
            elif col.resaltar_negativo and isinstance(v, (int, float, Decimal)) and float(v) < 0:
                estilo.add("TEXTCOLOR", (j, i), (j, i), HexColor("#" + _ROJO))
    tabla.setStyle(estilo)
    story.append(tabla)

    doc.build(story, canvasmaker=_LienzoNumerado)
    return buf.getvalue()
