"""
Orquesta un lote MIXTO de DBF: enruta cada archivo a su importador según el
tipo detectado por columnas (ICI / stock por lote / catálogo / CENARES) y
recalcula el CPMA UNA sola vez al final del lote.

Reusa los importadores existentes y probados (importar_ici, importar_mproducto,
importar_stock_almacen, importar_compra_centralizada) — acá solo hay
enrutamiento y el recálculo final; no se reescribe la lógica de importación.

Expone dos formas de la MISMA orquestación:
  - `importar_lote_mixto_stream`: generador que emite eventos de progreso
    (plan → archivo_inicio → archivo_fin → recalculo_inicio → fin) para dar
    feedback en vivo al doc, archivo por archivo.
  - `importar_lote_mixto`: envoltorio que consume el generador y devuelve el
    resumen final (para el endpoint no-streaming y las pruebas).
"""
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.etl.cenares import importar_compra_centralizada
from app.etl.deteccion_tipo import (
    TIPO_CATALOGO,
    TIPO_CENARES,
    TIPO_ICI,
    TIPO_MOVIM_CAB,
    TIPO_MOVIM_DET,
    TIPO_STOCK_ALMACEN,
    detectar_tipo_archivo,
)
from app.etl.ici import importar_ici
from app.etl.movimientos import importar_movimientos
from app.etl.mproducto import importar_mproducto
from app.etl.stock_almacen import importar_stock_almacen
from app.models.calc_cpma import CalcCpma
from app.models.stock_almacen import ORIGEN_ALMACEN, ORIGEN_EESS_LOTE
from app.repositories.cpma_repository import recalcular_cpma, recalcular_cpma_red
from app.repositories.dme_repository import recalcular_dme
from app.repositories.stock_repository import listar_vencimientos

# El catálogo se importa primero (para que ICI/stock resuelvan productos), luego
# el ICI (que crea los que falten), y al final el stock.
_ORDEN_TIPO = {TIPO_CATALOGO: 0, TIPO_ICI: 1, TIPO_STOCK_ALMACEN: 2, TIPO_CENARES: 3}


@dataclass
class ResumenArchivoMixto:
    archivo: str
    tipo: str
    importacion_id: int | None = None
    establecimiento: str | None = None
    filas: int = 0
    incidencias: int = 0
    estado: str = "OK"  # OK | ERROR | OMITIDO
    error: str | None = None
    detalle: str | None = None


@dataclass
class ResumenLoteMixto:
    archivos: list[ResumenArchivoMixto] = field(default_factory=list)
    productos_recalculados: int = 0
    productos_red_recalculados: int = 0
    establecimientos_dme_recalculados: int = 0
    modulos: list[dict] = field(default_factory=list)


def _arch_dict(a: ResumenArchivoMixto) -> dict:
    return {
        "archivo": a.archivo,
        "tipo": a.tipo,
        "importacion_id": a.importacion_id,
        "establecimiento": a.establecimiento,
        "filas": a.filas,
        "incidencias": a.incidencias,
        "estado": a.estado,
        "error": a.error,
        "detalle": a.detalle,
    }


def importar_lote_mixto_stream(
    db: Session,
    dbfs: list[tuple[str, Path]],
    asignaciones: dict[str, str],
    periodo: date,
    usuario: str | None = None,
) -> Iterator[dict]:
    """Generador de eventos de progreso. dbfs: (nombre, ruta). asignaciones:
    {nombre_archivo_ici: cod_2000}. El periodo aplica a los ICI (y como fecha de
    la foto del stock). Al final `return` el ResumenLoteMixto (StopIteration.value)."""
    lote = ResumenLoteMixto()
    pares_ici: set[tuple[int, int]] = set()
    productos_stock: set[int] = set()
    almacen_tocado = False
    ests_lote: set[str] = set()
    cenares_importado = False

    clasificados = [(nombre, ruta, detectar_tipo_archivo(ruta)) for nombre, ruta in dbfs]
    clasificados.sort(key=lambda x: _ORDEN_TIPO.get(x[2], 9))

    # Plan ordenado (lo que el doc verá procesarse, en orden).
    yield {
        "evento": "plan",
        "archivos": [{"archivo": nombre, "tipo": tipo} for nombre, _, tipo in clasificados],
    }

    # El detalle de movimientos (TMOVIMDET) se une a su cabecera (TMOVIM).
    ruta_cab_movim = next((r for _, r, t in clasificados if t == TIPO_MOVIM_CAB), None)
    movim_puesto: str | None = None

    for nombre, ruta, tipo in clasificados:
        yield {"evento": "archivo_inicio", "archivo": nombre, "tipo": tipo}
        entrada = ResumenArchivoMixto(archivo=nombre, tipo=tipo)
        try:
            if tipo == TIPO_CATALOGO:
                r = importar_mproducto(db, ruta)
                entrada.filas = r.filas_leidas
                entrada.detalle = f"{r.creados} creados, {r.actualizados} actualizados"

            elif tipo == TIPO_ICI:
                cod = asignaciones.get(nombre)
                if not cod:
                    entrada.estado = "OMITIDO"
                    entrada.error = "Sin establecimiento asignado"
                    lote.archivos.append(entrada)
                    yield {"evento": "archivo_fin", "resultado": _arch_dict(entrada)}
                    continue
                r = importar_ici(db, ruta, cod, periodo, usuario=usuario)
                entrada.importacion_id = r.importacion_id
                entrada.establecimiento = r.establecimiento
                entrada.filas = r.filas_leidas
                entrada.incidencias = r.incidencias
                entrada.detalle = f"{r.productos_promovidos} productos, {r.productos_creados} nuevos"
                pares_ici |= r.pares_afectados

            elif tipo == TIPO_STOCK_ALMACEN:
                r = importar_stock_almacen(db, ruta, periodo, usuario=usuario, recalcular=False)
                entrada.filas = sum(u.filas_leidas for u in r.ubicaciones)
                entrada.incidencias = sum(u.incidencias for u in r.ubicaciones)
                entrada.importacion_id = r.ubicaciones[0].importacion_id if r.ubicaciones else None
                entrada.detalle = "; ".join(
                    f"{u.ubicacion}: {u.lotes_promovidos} lotes importados"
                    + (f" · {u.lotes_fuera_catalogo} fuera de catálogo" if u.lotes_fuera_catalogo else "")
                    for u in r.ubicaciones
                )
                productos_stock |= r.productos_afectados
                for u in r.ubicaciones:
                    if u.origen == ORIGEN_ALMACEN:
                        almacen_tocado = True
                    else:
                        ests_lote.add(u.cod)

            elif tipo == TIPO_CENARES:
                r = importar_compra_centralizada(db, ruta)
                entrada.filas = sum(r.por_anio.values())
                entrada.detalle = ", ".join(f"{a}: {n}" for a, n in sorted(r.por_anio.items()))
                cenares_importado = True

            elif tipo == TIPO_MOVIM_CAB:
                # La cabecera se procesa junto con el detalle (no por sí sola).
                entrada.detalle = "cabecera de movimientos (se une al detalle)"

            elif tipo == TIPO_MOVIM_DET:
                if ruta_cab_movim is None:
                    entrada.estado = "OMITIDO"
                    entrada.error = "Falta el TMOVIM (cabecera) para unir los movimientos."
                    lote.archivos.append(entrada)
                    yield {"evento": "archivo_fin", "resultado": _arch_dict(entrada)}
                    continue
                r = importar_movimientos(db, ruta_cab_movim, ruta, usuario=usuario)
                entrada.importacion_id = r.importacion_id
                entrada.establecimiento = r.establecimiento_cod
                entrada.filas = r.lineas_leidas
                entrada.detalle = (
                    f"{r.establecimiento_nombre}: {r.movimientos} movimientos"
                    + (f" · {r.fuera_catalogo} fuera de catálogo" if r.fuera_catalogo else "")
                )
                movim_puesto = r.establecimiento_nombre

            else:
                entrada.estado = "OMITIDO"
                entrada.error = "Tipo de archivo no reconocido (no es ICI, stock, catálogo ni CENARES)."
        except Exception as exc:  # un archivo roto no bloquea el resto
            db.rollback()
            entrada.estado = "ERROR"
            entrada.error = str(exc)

        lote.archivos.append(entrada)
        yield {"evento": "archivo_fin", "resultado": _arch_dict(entrada)}

    # ── Recálculo del CPMA una sola vez al final ──────────────────────────
    pares = set(pares_ici)
    productos = {p for _, p in pares_ici} | productos_stock
    necesita_recalculo = bool(pares_ici or productos_stock)
    if necesita_recalculo:
        yield {"evento": "recalculo_inicio"}

    if productos_stock:
        # Cambios de stock (del almacén) afectan los pares (establecimiento, producto)
        # que ya existen en calc_cpma para esos productos.
        pares |= set(
            db.execute(
                select(CalcCpma.establecimiento_id, CalcCpma.producto_id).where(
                    CalcCpma.producto_id.in_(productos_stock)
                )
            ).all()
        )

    if pares:
        lote.productos_recalculados = recalcular_cpma(db, pares)
    if productos:
        lote.productos_red_recalculados = recalcular_cpma_red(db, productos)
        n_dme, _ = recalcular_dme(db, {e for e, _ in pares})
        lote.establecimientos_dme_recalculados = n_dme
    db.commit()

    lote.modulos = _modulos_actualizados(
        db, pares_ici, cenares_importado, almacen_tocado, ests_lote, lote, movim_puesto
    )

    yield {
        "evento": "fin",
        "resumen": {
            "archivos": [_arch_dict(a) for a in lote.archivos],
            "productos_recalculados": lote.productos_recalculados,
            "productos_red_recalculados": lote.productos_red_recalculados,
            "modulos": lote.modulos,
        },
    }
    return lote


def _modulos_actualizados(
    db: Session,
    pares_ici: set,
    cenares_importado: bool,
    almacen_tocado: bool,
    ests_lote: set[str],
    lote: ResumenLoteMixto,
    movim_puesto: str | None = None,
) -> list[dict]:
    """Qué módulos cambió este lote, con enlace directo para que el doc salte a
    ver el resultado."""
    modulos: list[dict] = []
    if movim_puesto:
        modulos.append({
            "pagina": "movimientos",
            "titulo": "Movimientos (kardex)",
            "detalle": f"Kardex de {movim_puesto} actualizado",
        })
    if pares_ici:
        modulos.append({
            "pagina": "disponibilidad",
            "titulo": "Disponibilidad actualizada",
            "detalle": f"{lote.productos_red_recalculados} productos recalculados a nivel de red",
        })
    if cenares_importado:
        modulos.append({
            "pagina": "consolidado",
            "titulo": "Consolidado de Red",
            "detalle": "Estado de compra CENARES actualizado",
        })
    if almacen_tocado or ests_lote:
        modulos.append({
            "pagina": "stock",
            "titulo": "Stock actualizado",
            "detalle": "Saldos por lote al día (con negativos ocultos)",
        })
        hoy = date.today()
        total_venc = 0
        if almacen_tocado:
            total_venc += len(listar_vencimientos(db, hoy, fuente=ORIGEN_ALMACEN))
        for cod in ests_lote:
            total_venc += len(
                listar_vencimientos(db, hoy, fuente=ORIGEN_EESS_LOTE, establecimiento_cod=cod)
            )
        if total_venc:
            modulos.append({
                "pagina": "vencimientos",
                "titulo": f"{total_venc} vencimiento{'s' if total_venc != 1 else ''} por revisar",
                "detalle": "Lotes vencidos o próximos a vencer en el stock cargado",
            })
    return modulos


def importar_lote_mixto(
    db: Session,
    dbfs: list[tuple[str, Path]],
    asignaciones: dict[str, str],
    periodo: date,
    usuario: str | None = None,
) -> ResumenLoteMixto:
    """Versión no-streaming: consume el generador y devuelve el resumen final."""
    gen = importar_lote_mixto_stream(db, dbfs, asignaciones, periodo, usuario=usuario)
    try:
        while True:
            next(gen)
    except StopIteration as fin:
        return fin.value
