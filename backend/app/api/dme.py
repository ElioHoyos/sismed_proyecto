"""GET /api/dme — % DME por establecimiento y consolidado de red.
Todo lee de calc_dme/calc_dme_red, precalculado en cada importación (ver
app/repositories/dme_repository.py) — nada se calcula al vuelo aquí."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.dme_repository import listar_dme, obtener_dme_red

router = APIRouter(prefix="/api/dme", tags=["dme"])


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


class DmeEstablecimientoOut(BaseModel):
    establecimiento_cod: str
    establecimiento_nombre: str
    total_evaluados: int
    total_disponibles: int
    porcentaje: float
    semaforo: str


class DmeListOut(BaseModel):
    periodo: str | None
    total: int
    resultados: list[DmeEstablecimientoOut]


class DmeRedOut(BaseModel):
    periodo: str | None
    total_evaluados: int
    total_disponibles: int
    porcentaje: float
    semaforo: str


@router.get("", response_model=DmeListOut)
def obtener_dme(
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente disponible"),
    db: Session = Depends(get_db),
) -> DmeListOut:
    periodo_usado, filas = listar_dme(db, _parsear_periodo_opcional(periodo))
    return DmeListOut(
        periodo=periodo_usado.strftime("%Y-%m") if periodo_usado else None,
        total=len(filas),
        resultados=[DmeEstablecimientoOut(**f) for f in filas],
    )


@router.get("/red", response_model=DmeRedOut)
def obtener_dme_red_endpoint(
    periodo: str | None = Query(None, description="AAAA-MM; por defecto el más reciente disponible"),
    db: Session = Depends(get_db),
) -> DmeRedOut:
    resultado = obtener_dme_red(db, _parsear_periodo_opcional(periodo))
    if resultado is None:
        raise HTTPException(status_code=404, detail="No hay DME calculado para ese periodo")
    return DmeRedOut(
        periodo=resultado["periodo"].strftime("%Y-%m"),
        total_evaluados=resultado["total_evaluados"],
        total_disponibles=resultado["total_disponibles"],
        porcentaje=resultado["porcentaje"],
        semaforo=resultado["semaforo"],
    )
