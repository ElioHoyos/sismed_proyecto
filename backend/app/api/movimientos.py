"""Módulo de Movimientos (kardex): kardex por producto con saldo corriente,
consumo fino (día/semana/mes) con comparación contra el CPMA, y clasificación de
salidas por categoría. Nunca expone datos de paciente (la tabla no los tiene)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.movimiento_repository import (
    clasificacion_salidas,
    consumo,
    cpma_de_referencia,
    establecimientos_con_movimientos,
    kardex,
    resolver_producto,
)

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])


def _fecha(v: str | None) -> date | None:
    if not v:
        return None
    try:
        a, m, d = v.split("-")
        return date(int(a), int(m), int(d))
    except (ValueError, AttributeError):
        raise HTTPException(400, f"fecha inválida: {v!r} (esperado AAAA-MM-DD)")


class EstablecimientoOut(BaseModel):
    cod_2000: str
    nombre: str


class ProductoInfo(BaseModel):
    producto_cod: str
    producto_nombre: str
    codigo_siga: str | None


@router.get("/establecimientos", response_model=list[EstablecimientoOut])
def obtener_establecimientos(db: Session = Depends(get_db)) -> list[EstablecimientoOut]:
    """Puestos que aportaron movimientos (kardex)."""
    return [EstablecimientoOut(**e) for e in establecimientos_con_movimientos(db)]


# ── PASO 2: Kardex ─────────────────────────────────────────────────────────

class KardexRow(BaseModel):
    fecha: str | None
    tipo: str  # E | S
    lote: str | None
    fecha_vcto: str | None
    cantidad: float
    categoria: str | None
    establecimiento_cod: str | None
    establecimiento_nombre: str | None
    saldo: float


class KardexOut(BaseModel):
    producto: ProductoInfo
    total: int
    resultados: list[KardexRow]


@router.get("/kardex", response_model=KardexOut)
def obtener_kardex(
    producto: str = Query(..., description="Nombre, código o SIGA del producto"),
    establecimiento_cod: str | None = Query(None),
    desde: str | None = Query(None, description="AAAA-MM-DD"),
    hasta: str | None = Query(None, description="AAAA-MM-DD"),
    db: Session = Depends(get_db),
) -> KardexOut:
    p = resolver_producto(db, producto)
    if p is None:
        raise HTTPException(404, f"No se encontró un producto para {producto!r}.")
    filas = kardex(db, p, establecimiento_cod, _fecha(desde), _fecha(hasta))
    return KardexOut(
        producto=ProductoInfo(producto_cod=p.medcod, producto_nombre=p.nombre, codigo_siga=p.codigo_siga),
        total=len(filas),
        resultados=[
            KardexRow(
                **{
                    **f,
                    "fecha": f["fecha"].isoformat() if f["fecha"] else None,
                    "fecha_vcto": f["fecha_vcto"].isoformat() if f["fecha_vcto"] else None,
                }
            )
            for f in filas
        ],
    )


# ── PASO 3: Consumo fino ───────────────────────────────────────────────────

class ConsumoPunto(BaseModel):
    periodo: str
    salidas: float
    movimientos: int


class ConsumoOut(BaseModel):
    producto: ProductoInfo
    granularidad: str
    cpma_referencia: float | None  # CPMA calculado (red), para validación cruzada
    total_salidas: float
    resultados: list[ConsumoPunto]


@router.get("/consumo", response_model=ConsumoOut)
def obtener_consumo(
    producto: str = Query(...),
    establecimiento_cod: str | None = Query(None),
    granularidad: str = Query("mes", description="dia | semana | mes"),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ConsumoOut:
    if granularidad not in ("dia", "semana", "mes"):
        raise HTTPException(400, "granularidad debe ser 'dia', 'semana' o 'mes'.")
    p = resolver_producto(db, producto)
    if p is None:
        raise HTTPException(404, f"No se encontró un producto para {producto!r}.")
    puntos = consumo(db, p, establecimiento_cod, granularidad, _fecha(desde), _fecha(hasta))
    return ConsumoOut(
        producto=ProductoInfo(producto_cod=p.medcod, producto_nombre=p.nombre, codigo_siga=p.codigo_siga),
        granularidad=granularidad,
        cpma_referencia=cpma_de_referencia(db, p),
        total_salidas=sum(pt["salidas"] for pt in puntos),
        resultados=[ConsumoPunto(**pt) for pt in puntos],
    )


# ── PASO 4: Clasificación de salidas ───────────────────────────────────────

class ClasificacionItem(BaseModel):
    categoria: str
    salidas: float
    movimientos: int


class ClasificacionOut(BaseModel):
    producto: ProductoInfo
    total_salidas: float
    resultados: list[ClasificacionItem]


@router.get("/clasificacion", response_model=ClasificacionOut)
def obtener_clasificacion(
    producto: str = Query(...),
    establecimiento_cod: str | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
) -> ClasificacionOut:
    p = resolver_producto(db, producto)
    if p is None:
        raise HTTPException(404, f"No se encontró un producto para {producto!r}.")
    items = clasificacion_salidas(db, p, establecimiento_cod, _fecha(desde), _fecha(hasta))
    return ClasificacionOut(
        producto=ProductoInfo(producto_cod=p.medcod, producto_nombre=p.nombre, codigo_siga=p.codigo_siga),
        total_salidas=sum(i["salidas"] for i in items),
        resultados=[ClasificacionItem(**i) for i in items],
    )
