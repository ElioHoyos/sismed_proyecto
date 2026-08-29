"""Módulo de Stock unificado: stock del ALMACÉN (por lote, con vencimiento) o de
un ESTABLECIMIENTO (por producto, sin lote), según el filtro `origen`. Un mismo
endpoint sirve la vista completa y la de saldos negativos (`solo_negativos`)."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.stock_almacen import ORIGEN_ALMACEN, ORIGEN_EESS, ORIGEN_EESS_LOTE
from app.repositories.historial_stock_repository import (
    listar_historial,
    marcar_revision,
    quitar_revision,
    resumen_mensual,
)
from app.repositories.stock_repository import (
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    VENTANA_PROXIMO_DIAS,
    establecimientos_con_lote,
    listar_fuera_catalogo,
    listar_stock,
    listar_vencimientos,
    stock_es_por_lote,
)

router = APIRouter(prefix="/api/stock", tags=["stock"])


class StockRowOut(BaseModel):
    origen: str  # ALMACEN | EESS
    producto_cod: str
    producto_nombre: str
    codigo_siga: str | None
    medtip: str | None  # M/I
    medpet: str | None  # P/_
    medest: str | None  # E/S/_
    establecimiento_cod: str | None  # solo EESS
    establecimiento_nombre: str | None  # solo EESS
    almacen_cod: str | None  # solo ALMACEN
    lote: str | None  # solo ALMACEN (el ICI no trae lote)
    fecha_vcto: str | None  # solo ALMACEN
    saldo: float
    saldo_consolidado: float  # total del producto (para evidenciar negativos ocultos)
    incidencia_id: int | None  # incidencia de historial (solo negativos por lote)
    revisado: bool  # check del informático (misma tabla que el Historial)
    revisado_en: str | None  # fecha/hora del check
    nota: str | None  # nota opcional del check


class StockListOut(BaseModel):
    origen: str
    por_lote: bool  # True = filas por lote (almacén, o EESS con MSTKALMDE cargado)
    total: int
    resultados: list[StockRowOut]


class EstablecimientoConLoteOut(BaseModel):
    cod_2000: str
    nombre: str


def _validar_tipo(tipo: str | None) -> str | None:
    if tipo in (None, ""):
        return None
    t = tipo.upper()
    if t not in ("M", "I"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'M' o 'I'.")
    return t


def _validar_financiamiento(financiamiento: str | None) -> str | None:
    if financiamiento in (None, ""):
        return None
    if financiamiento not in ("P", "_"):
        raise HTTPException(status_code=400, detail="financiamiento debe ser 'P' o '_'.")
    return financiamiento


def _validar_medest(medest: str | None) -> str | None:
    if medest in (None, ""):
        return None
    if medest not in ("S", "_", "E"):
        raise HTTPException(status_code=400, detail="medest debe ser 'S', '_' o 'E'.")
    return medest


@router.get("", response_model=StockListOut)
def obtener_stock(
    origen: str = Query(..., description="ALMACEN o EESS"),
    establecimiento_cod: str | None = Query(
        None, description="Solo EESS: un puesto; si se omite, todos los puestos"
    ),
    solo_negativos: bool = Query(False, description="Solo saldos negativos"),
    tipo: str | None = Query(None, description="MEDTIP: M (medicamento) o I (insumo)"),
    financiamiento: str | None = Query(None, description="MEDPET: P (petitorio) o _ (SIS)"),
    medest: str | None = Query(None, description="MEDEST: S (soporte), _ (SIS) o E (estratégico)"),
    db: Session = Depends(get_db),
) -> StockListOut:
    origen = origen.upper()
    if origen not in (ORIGEN_ALMACEN, ORIGEN_EESS):
        raise HTTPException(status_code=400, detail="origen debe ser 'ALMACEN' o 'EESS'.")

    est_cod = establecimiento_cod if origen == ORIGEN_EESS else None
    filas = listar_stock(
        db,
        origen=origen,
        establecimiento_cod=est_cod,
        solo_negativos=solo_negativos,
        tipo=_validar_tipo(tipo),
        financiamiento=_validar_financiamiento(financiamiento),
        medest=_validar_medest(medest),
    )
    return StockListOut(
        origen=origen,
        por_lote=stock_es_por_lote(db, origen, est_cod),
        total=len(filas),
        resultados=[
            StockRowOut(
                **{**f, "fecha_vcto": f["fecha_vcto"].isoformat() if f["fecha_vcto"] else None}
            )
            for f in filas
        ],
    )


@router.get("/establecimientos-con-lote", response_model=list[EstablecimientoConLoteOut])
def obtener_establecimientos_con_lote(db: Session = Depends(get_db)) -> list[EstablecimientoConLoteOut]:
    """Establecimientos que aportaron stock por lote (MSTKALMDE) — los únicos con
    negativos por lote y vencimientos. Los de solo-ICI no aparecen."""
    return [EstablecimientoConLoteOut(**e) for e in establecimientos_con_lote(db)]


class FueraCatalogoRowOut(BaseModel):
    medcod: str
    lote: str
    fecha_vcto: str | None
    saldo: float
    precio: float | None
    reg_sanitario: str | None
    establecimiento_cod: str | None
    establecimiento_nombre: str | None


class FueraCatalogoOut(BaseModel):
    origen: str
    total: int
    resultados: list[FueraCatalogoRowOut]


@router.get("/fuera-catalogo", response_model=FueraCatalogoOut)
def obtener_fuera_catalogo(
    origen: str = Query("EESS", description="ALMACEN o EESS"),
    establecimiento_cod: str | None = Query(None, description="Solo EESS: un puesto; si se omite, todos"),
    db: Session = Depends(get_db),
) -> FueraCatalogoOut:
    """Productos con stock por lote que NO están en el catálogo del almacén (dato
    a revisar, no error): el puesto los maneja por vía externa (DIRESA/CENARES/
    donación). No se importan ni se crean en el catálogo central."""
    origen = origen.upper()
    if origen not in (ORIGEN_ALMACEN, ORIGEN_EESS):
        raise HTTPException(status_code=400, detail="origen debe ser 'ALMACEN' o 'EESS'.")
    filas = listar_fuera_catalogo(
        db, origen, establecimiento_cod if origen == ORIGEN_EESS else None
    )
    return FueraCatalogoOut(
        origen=origen,
        total=len(filas),
        resultados=[
            FueraCatalogoRowOut(
                **{**f, "fecha_vcto": f["fecha_vcto"].isoformat() if f["fecha_vcto"] else None}
            )
            for f in filas
        ],
    )


class VencimientoOut(BaseModel):
    codigo_siga: str | None
    producto_cod: str
    producto_nombre: str
    medtip: str | None  # M/I
    medpet: str | None  # P/_
    medest: str | None  # E/S/_
    lote: str
    fecha_vcto: str
    dias_restantes: int  # negativo si ya venció
    saldo: float  # unidades
    estado: str  # VENCIDO | PROXIMO_A_VENCER
    origen: str  # ALMACEN | EESS_LOTE
    establecimiento_cod: str | None  # solo EESS_LOTE
    establecimiento_nombre: str | None  # solo EESS_LOTE
    almacen_cod: str | None  # solo ALMACEN


class VencimientosListOut(BaseModel):
    hoy: str  # fecha de referencia del cálculo (tiempo de consulta)
    ventana_dias: int
    fuente: str  # ALMACEN | EESS
    total: int
    resultados: list[VencimientoOut]


@router.get("/vencimientos", response_model=VencimientosListOut)
def obtener_vencimientos(
    estado: str | None = Query(
        None, description="VENCIDO o PROXIMO_A_VENCER; si se omite, ambos"
    ),
    fuente: str = Query(
        "ALMACEN", description="ALMACEN (almacén central) o EESS (establecimientos con stock por lote)"
    ),
    establecimiento_cod: str | None = Query(
        None, description="Solo con fuente=EESS: un puesto; si se omite, todos los que aportaron lote"
    ),
    tipo: str | None = Query(None, description="MEDTIP: M (medicamento) o I (insumo)"),
    financiamiento: str | None = Query(None, description="MEDPET: P (petitorio) o _ (SIS)"),
    medest: str | None = Query(None, description="MEDEST: S (soporte), _ (SIS) o E (estratégico)"),
    db: Session = Depends(get_db),
) -> VencimientosListOut:
    """Lotes con stock > 0 vencidos o próximos a vencer (contra la fecha actual).
    Del almacén central (`fuente=ALMACEN`) o de los establecimientos que
    aportaron stock por lote (`fuente=EESS`) — el ICI no trae lote ni vencimiento."""
    estado_norm = estado.upper() if estado else None
    if estado_norm and estado_norm not in (ESTADO_VENCIDO, ESTADO_PROXIMO):
        raise HTTPException(
            status_code=400, detail="estado debe ser 'VENCIDO' o 'PROXIMO_A_VENCER'."
        )
    fuente = fuente.upper()
    if fuente not in ("ALMACEN", "EESS"):
        raise HTTPException(status_code=400, detail="fuente debe ser 'ALMACEN' o 'EESS'.")
    fuente_origen = ORIGEN_ALMACEN if fuente == "ALMACEN" else ORIGEN_EESS_LOTE

    hoy = date.today()
    filas = listar_vencimientos(
        db,
        hoy,
        estado_norm,
        tipo=_validar_tipo(tipo),
        financiamiento=_validar_financiamiento(financiamiento),
        medest=_validar_medest(medest),
        fuente=fuente_origen,
        establecimiento_cod=establecimiento_cod if fuente == "EESS" else None,
    )
    return VencimientosListOut(
        hoy=hoy.isoformat(),
        ventana_dias=VENTANA_PROXIMO_DIAS,
        fuente=fuente,
        total=len(filas),
        resultados=[
            VencimientoOut(**{**f, "fecha_vcto": f["fecha_vcto"].isoformat()}) for f in filas
        ],
    )


# ── Historial de correcciones (negativos por lote) ─────────────────────────

def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, datetime) else None


class HistorialRowOut(BaseModel):
    id: int
    tipo: str
    origen: str
    almacen_cod: str | None
    establecimiento_cod: str | None
    establecimiento_nombre: str | None
    producto_cod: str
    producto_nombre: str
    codigo_siga: str | None
    lote: str
    estado: str  # PENDIENTE | RESUELTO
    detectado_en: str
    detectado_inicial: bool  # sembrado del stock preexistente (fecha aproximada)
    valor_detectado: float
    valor_actual: float
    resuelto_en: str | None
    valor_resuelto: float | None
    dias: int  # días abierto (hasta resolverse o hasta hoy)
    revisado: bool
    revisado_por: str | None
    revisado_en: str | None
    nota: str | None


class HistorialListOut(BaseModel):
    estado: str
    total: int
    resultados: list[HistorialRowOut]


class HistorialResumenOut(BaseModel):
    mes: str
    negativos: int
    resueltos: int
    pendientes: int
    pendientes_totales: int


@router.get("/historial", response_model=HistorialListOut)
def obtener_historial(
    estado: str = Query("todos", description="pendientes | resueltos | todos"),
    origen: str | None = Query(None, description="ALMACEN o EESS_LOTE"),
    establecimiento_cod: str | None = Query(None),
    mes: str | None = Query(None, description="AAAA-MM: incidencias detectadas en ese mes"),
    db: Session = Depends(get_db),
) -> HistorialListOut:
    """Línea de vida de cada negativo por lote: detectado → revisado → resuelto.
    El 'resuelto' se detecta solo comparando cargas; el 'revisado' es el check
    del informático."""
    estado = estado.lower()
    if estado not in ("pendientes", "resueltos", "todos"):
        raise HTTPException(status_code=400, detail="estado debe ser 'pendientes', 'resueltos' o 'todos'.")
    filas = listar_historial(db, estado=estado, origen=origen, establecimiento_cod=establecimiento_cod, mes=mes)
    return HistorialListOut(
        estado=estado,
        total=len(filas),
        resultados=[
            HistorialRowOut(
                **{
                    **f,
                    "detectado_en": _iso(f["detectado_en"]),
                    "resuelto_en": _iso(f["resuelto_en"]),
                    "revisado_en": _iso(f["revisado_en"]),
                }
            )
            for f in filas
        ],
    )


@router.get("/historial/resumen", response_model=HistorialResumenOut)
def obtener_historial_resumen(
    mes: str = Query(..., description="AAAA-MM"),
    db: Session = Depends(get_db),
) -> HistorialResumenOut:
    return HistorialResumenOut(**resumen_mensual(db, mes))


class RevisionIn(BaseModel):
    revisado_por: str | None = None
    nota: str | None = None


@router.put("/historial/{incidencia_id}/revision")
def poner_revision(incidencia_id: int, payload: RevisionIn, db: Session = Depends(get_db)) -> dict:
    """El informático marca la incidencia como revisada/corregida (quién + nota)."""
    if not marcar_revision(db, incidencia_id, payload.revisado_por, payload.nota):
        raise HTTPException(status_code=404, detail="Incidencia no encontrada.")
    return {"ok": True}


@router.delete("/historial/{incidencia_id}/revision")
def sacar_revision(incidencia_id: int, db: Session = Depends(get_db)) -> dict:
    """Quita el check de revisado."""
    quitar_revision(db, incidencia_id)
    return {"ok": True}
