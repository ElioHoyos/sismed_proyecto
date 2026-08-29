"""Disponibilidad, vista de red y requisición sugerida — todo lee de
calc_cpma/calc_cpma_red, salvo la fórmula final de requisición."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.disponibilidad_repository import (
    listar_disponibilidad,
    listar_disponibilidad_red,
    obtener_requisicion,
    resumen_situacion_red,
)
from app.services.cpma import MESES_A_CUBRIR_DEFAULT

router = APIRouter(prefix="/api", tags=["disponibilidad"])

# El stock del almacén central es UNO SOLO, compartido por los 89
# establecimientos — se repite en el cálculo de cada uno (ver
# calc_cpma.stock), no se reparte entre ellos. Un establecimiento en
# SOBRESTOCK asume acceso a TODO el almacén, no que ese stock sea suyo
# en exclusiva. El % de situación real de la red sale de
# /api/disponibilidad/red/resumen, nunca de contar filas de esta vista.
NOTA_STOCK_COMPARTIDO = (
    "El stock del almacén central es compartido entre todos los establecimientos: "
    "esta disponibilidad asume acceso al total del almacén, no que sea exclusivo de "
    "este establecimiento. Para el % de situación real de la red, usar "
    "GET /api/disponibilidad/red/resumen — nunca contar/agrupar filas de esta vista."
)


def _parsear_periodo_opcional(periodo: str | None) -> date | None:
    if periodo is None:
        return None
    try:
        anio_str, mes_str = periodo.split("-")
        return date(int(anio_str), int(mes_str), 1)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400, detail=f"periodo inválido: {periodo!r}, formato esperado AAAA-MM"
        )


class MesConsumo(BaseModel):
    anio: int
    mes: int
    nombre: str
    consumo: float


class DisponibilidadOut(BaseModel):
    establecimiento_cod: str
    establecimiento_nombre: str
    producto_cod: str
    producto_nombre: str
    codigo_siga: str | None  # CODIGO SIGA
    medtip: str | None  # M/I
    medpet: str | None  # P/_
    medest: str | None  # E/S/_
    ff: str | None  # forma farmacéutica
    sumames: float
    contador: int
    cpma: float
    stock_red: float  # stock de la Red (establecimiento)
    stock_aem: float  # Almacén Especializado de Medicamentos (central)
    dispo: float  # stock_red / cpma
    dispo_total: float  # (stock_red + stock_aem) / cpma
    situacion: str
    situacion_total: str
    meses: list[MesConsumo]


class DisponibilidadListOut(BaseModel):
    periodo: str | None
    total: int
    nota: str = NOTA_STOCK_COMPARTIDO
    resultados: list[DisponibilidadOut]


@router.get("/disponibilidad", response_model=DisponibilidadListOut)
def obtener_disponibilidad(
    establecimiento_cod: str | None = None,
    producto_cod: str | None = None,
    situacion: str | None = None,
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente disponible"),
    db: Session = Depends(get_db),
) -> DisponibilidadListOut:
    periodo_usado, filas = listar_disponibilidad(
        db,
        establecimiento_cod=establecimiento_cod,
        producto_cod=producto_cod,
        situacion=situacion,
        periodo=_parsear_periodo_opcional(periodo),
    )
    return DisponibilidadListOut(
        periodo=periodo_usado.strftime("%Y-%m") if periodo_usado else None,
        total=len(filas),
        resultados=[DisponibilidadOut(**f) for f in filas],
    )


class DisponibilidadRedOut(BaseModel):
    producto_cod: str
    producto_nombre: str
    codigo_siga: str | None  # CODIGO SIGA
    medtip: str | None  # M/I
    medpet: str | None  # P/_
    medest: str | None  # E/S/_
    ff: str | None  # forma farmacéutica
    sumames: float
    contador: int
    cpma: float
    stock_red: float  # stock de la Red (suma de establecimientos)
    stock_aem: float  # Almacén Especializado de Medicamentos (central)
    dispo: float  # stock_red / cpma
    dispo_total: float  # (stock_red + stock_aem) / cpma
    situacion: str
    situacion_total: str
    meses: list[MesConsumo]


class DisponibilidadRedListOut(BaseModel):
    periodo: str | None
    total: int
    resultados: list[DisponibilidadRedOut]


@router.get("/disponibilidad/red", response_model=DisponibilidadRedListOut)
def obtener_disponibilidad_red(
    producto_cod: str | None = None,
    situacion: str | None = None,
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente disponible"),
    db: Session = Depends(get_db),
) -> DisponibilidadRedListOut:
    periodo_usado, filas = listar_disponibilidad_red(
        db, producto_cod=producto_cod, situacion=situacion, periodo=_parsear_periodo_opcional(periodo),
    )
    return DisponibilidadRedListOut(
        periodo=periodo_usado.strftime("%Y-%m") if periodo_usado else None,
        total=len(filas),
        resultados=[DisponibilidadRedOut(**f) for f in filas],
    )


class SituacionResumenItem(BaseModel):
    situacion: str
    cantidad: int
    porcentaje: float


class ResumenSituacionRedOut(BaseModel):
    periodo: str | None
    # Dos indicadores independientes por MEDEST (Estratégicos excluidos):
    total_soporte: int
    total_sis: int
    soporte: list[SituacionResumenItem]
    sis: list[SituacionResumenItem]


@router.get("/disponibilidad/red/resumen", response_model=ResumenSituacionRedOut)
def obtener_resumen_situacion_red(
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente disponible"),
    db: Session = Depends(get_db),
) -> ResumenSituacionRedOut:
    """% de situación de la red, dividido en Soporte (S) y SIS (_) — dos
    indicadores independientes; los Estratégicos (E) se excluyen. Fuente:
    calc_cpma_red (una fila por producto)."""
    periodo_usado, r = resumen_situacion_red(db, _parsear_periodo_opcional(periodo))
    return ResumenSituacionRedOut(
        periodo=periodo_usado.strftime("%Y-%m") if periodo_usado else None,
        total_soporte=r["total_soporte"],
        total_sis=r["total_sis"],
        soporte=[SituacionResumenItem(**f) for f in r["soporte"]],
        sis=[SituacionResumenItem(**f) for f in r["sis"]],
    )


class RequisicionOut(BaseModel):
    nivel: str  # "establecimiento" | "red"
    establecimiento_cod: str | None
    producto_cod: str
    producto_nombre: str
    periodo: str
    cpma: float
    stock_disponible: float
    meses_a_cubrir: int
    cantidad_requerida: float
    nota: str | None = None


@router.get("/requisicion", response_model=RequisicionOut)
def obtener_requisicion_endpoint(
    producto_cod: str,
    establecimiento_cod: str | None = Query(
        None, description="Si se omite, la requisición es de RED (almacén central)"
    ),
    meses_a_cubrir: int = Query(MESES_A_CUBRIR_DEFAULT, ge=1),
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente disponible"),
    db: Session = Depends(get_db),
) -> RequisicionOut:
    resultado = obtener_requisicion(
        db,
        producto_cod=producto_cod,
        establecimiento_cod=establecimiento_cod,
        periodo=_parsear_periodo_opcional(periodo),
        meses_a_cubrir=meses_a_cubrir,
    )
    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay CPMA calculado para producto={producto_cod!r} "
                f"establecimiento={establecimiento_cod!r} periodo={periodo!r}"
            ),
        )
    resultado["periodo"] = resultado["periodo"].strftime("%Y-%m")
    resultado["nota"] = NOTA_STOCK_COMPARTIDO if resultado["nivel"] == "establecimiento" else None
    return RequisicionOut(**resultado)
