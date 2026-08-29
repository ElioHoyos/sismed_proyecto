"""Consolidado de Red: la vista que el doc arma a mano (DISPO_RED…ConCompra),
cruzando ICI + cálculos (calc_cpma_red) + CENARES. A nivel de red, nunca por
establecimiento. Lectura, edición inline de campos de compra, y export a Excel
idéntico a su formato (con encabezados de grupo)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.compra_repository import anios_disponibles
from app.repositories.consolidado_repository import listar_consolidado
from app.services.exportar import (
    SITUACION_COLORES,
    XLSX_MEDIA,
    Columna,
    generar_excel,
    nombre_archivo,
)

router = APIRouter(prefix="/api/consolidado-red", tags=["consolidado-red"])


def _periodo(p: str | None) -> date | None:
    if not p:
        return None
    try:
        a, m = p.split("-")
        return date(int(a), int(m), 1)
    except (ValueError, AttributeError):
        raise HTTPException(400, f"periodo inválido: {p!r}")


class CompraBloque(BaseModel):
    tipo_producto: str | None
    procedimiento: str | None
    estado_situacion: str | None
    observacion_estado: str | None
    fecha_convocatoria: str | None
    fecha_buena_pro: str | None
    reg_siga_situacion: str | None
    reg_siga_observacion: str | None
    contratista: str | None
    nro_contrato: str | None
    fecha_entrega_texto: str | None
    observacion: str | None
    editados: list[str]
    sin_registro: bool


class MesConsumo(BaseModel):
    anio: int
    mes: int
    nombre: str
    consumo: float


class ConsolidadoRow(BaseModel):
    codigo_siga: str | None
    producto_cod: str
    producto_nombre: str
    medtip: str | None
    medpet: str | None
    medest: str | None
    meses: list[MesConsumo]
    precio: float
    sumames: float
    contador: int
    cpma: float
    stock_red: float
    stock_aem: float
    dispo: float
    dispo_total: float
    situacion: str
    situacion_total: str
    compra: CompraBloque


class ConsolidadoOut(BaseModel):
    periodo: str | None
    compra_anio: int | None
    anios_compra: list[int]
    total: int
    resultados: list[ConsolidadoRow]


@router.get("", response_model=ConsolidadoOut)
def obtener_consolidado(
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente"),
    compra_anio: int | None = Query(None, description="Año de compra CENARES a cruzar"),
    db: Session = Depends(get_db),
) -> ConsolidadoOut:
    anios = anios_disponibles(db)
    if compra_anio is None:
        compra_anio = anios[0] if anios else None
    per_usado, filas = listar_consolidado(db, _periodo(periodo), compra_anio)
    return ConsolidadoOut(
        periodo=per_usado.strftime("%Y-%m") if per_usado else None,
        compra_anio=compra_anio,
        anios_compra=anios,
        total=len(filas),
        resultados=[ConsolidadoRow(**f) for f in filas],
    )


# ── Export a Excel (formato idéntico al del doc, con encabezados de grupo) ──

def _fecha_txt(v: str | None) -> str | None:
    """F.CONV/F.BP pueden ser fecha (ISO) o texto libre. Formatea la fecha a
    dd/mm/aaaa y deja el texto tal cual (para no perder 'NOVIEMBRE 2026')."""
    if not v:
        return None
    try:
        return date.fromisoformat(v[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return v


def _flatten(filas: list[dict]) -> list[Columna]:
    cols_mes: list[Columna] = []
    if filas:
        for i, m in enumerate(filas[0]["meses"]):
            cols_mes.append(Columna(f"_mes{i}", m["nombre"][:3].capitalize(), "entero"))
    for f in filas:
        for i, m in enumerate(f["meses"]):
            f[f"_mes{i}"] = m["consumo"]
        c = f["compra"]
        f["c_tipo"] = c["tipo_producto"]
        f["c_proc"] = c["procedimiento"]
        f["c_estado"] = "Sin compra centralizada" if c["sin_registro"] else c["estado_situacion"]
        f["c_obs_estado"] = c["observacion_estado"]
        f["c_reg_sit"] = c["reg_siga_situacion"]
        f["c_reg_obs"] = c["reg_siga_observacion"]
        f["c_contratista"] = c["contratista"]
        f["c_contrato"] = c["nro_contrato"]
        f["c_fconv"] = _fecha_txt(c["fecha_convocatoria"])
        f["c_fbp"] = _fecha_txt(c["fecha_buena_pro"])
        f["c_fent"] = c["fecha_entrega_texto"]
        f["c_obs"] = c["observacion"]
    return cols_mes


@router.get("/export")
def exportar_consolidado(
    periodo: str | None = Query(None),
    compra_anio: int | None = Query(None),
    db: Session = Depends(get_db),
):
    anios = anios_disponibles(db)
    if compra_anio is None:
        compra_anio = anios[0] if anios else None
    per_usado, filas = listar_consolidado(db, _periodo(periodo), compra_anio)
    cols_mes = _flatten(filas)

    columnas = (
        [
            Columna("codigo_siga", "CODIGO SIGA"),
            Columna("producto_cod", "CODIGO MEDICAMENTO"),
            Columna("producto_nombre", "MEDICAMENTO"),
            Columna("medtip", "M/I"),
            Columna("medpet", "_/P"),
            Columna("medest", "E/S/_"),
        ]
        + cols_mes
        + [
            Columna("precio", "PRECIO", "decimal"),
            Columna("sumames", "SUMAMES", "entero"),
            Columna("contador", "CONTADOR", "entero"),
            Columna("cpma", "CPA", "decimal"),
            Columna("stock_red", "STOCK", "entero"),
            Columna("stock_aem", "Stock_AEM", "entero"),
            Columna("dispo", "DISPO", "decimal"),
            Columna("situacion", "SITUACION", colores=SITUACION_COLORES),
            Columna("dispo_total", "DISPO_TOTAL", "decimal"),
            Columna("situacion_total", "SITUACION_TOTAL", colores=SITUACION_COLORES),
        ]
        + [
            Columna("c_tipo", "TIPO PRODUCTO"),
            Columna("c_proc", "PROCEDIMIENTO"),
            Columna("c_estado", "ESTADO"),
            Columna("c_obs_estado", "OBS ESTADO"),
            Columna("c_reg_sit", "REG.SIGA SITUACION"),
            Columna("c_reg_obs", "REG.SIGA OBSERVACION"),
            Columna("c_contratista", "CONTRATISTA"),
            Columna("c_contrato", "NRO CONTRATO"),
            Columna("c_fconv", "F.CONV"),
            Columna("c_fbp", "F.BP"),
            Columna("c_fent", "F.ENT"),
            Columna("c_obs", "OBSERVACION"),
        ]
    )
    grupos = [
        ("PRODUCTO", 6),
        ("CONSUMO 12 MESES", len(cols_mes)),
        ("CÁLCULO", 4),
        ("DISPONIBILIDAD", 6),
        (f"ESTADO COMPRA {compra_anio}" if compra_anio else "ESTADO COMPRA", 12),
    ]
    per_txt = per_usado.strftime("%Y-%m") if per_usado else "—"
    meta = [
        ("Vista", "Consolidado de red (Red + AEM + CENARES)"),
        ("Periodo", per_txt),
        ("Estado compra CENARES", str(compra_anio) if compra_anio else "—"),
    ]
    contenido = generar_excel("Consolidado de Red", meta, columnas, filas, grupos=grupos)
    nombre = nombre_archivo("consolidado-red", [per_txt, f"compra{compra_anio}" if compra_anio else ""], "xlsx")
    return Response(
        contenido,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
