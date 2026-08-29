"""GET /api/establecimientos — catálogo activo (sin el almacén) para poblar
selectores en el front (corrección de detección en la carga de ICI, etc.)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.establecimiento import Establecimiento

router = APIRouter(prefix="/api/establecimientos", tags=["establecimientos"])


class EstablecimientoOut(BaseModel):
    cod_2000: str
    nombre: str


@router.get("", response_model=list[EstablecimientoOut])
def listar_establecimientos(db: Session = Depends(get_db)) -> list[EstablecimientoOut]:
    filas = db.scalars(
        select(Establecimiento)
        .where(Establecimiento.activo, Establecimiento.es_almacen.is_(False))
        .order_by(Establecimiento.nombre)
    ).all()
    return [EstablecimientoOut(cod_2000=e.cod_2000, nombre=e.nombre) for e in filas]
