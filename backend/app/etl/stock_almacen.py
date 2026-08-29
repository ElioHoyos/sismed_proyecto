"""
Importador del stock por lote (SISMED: MSTKALMDE.DBF). Sirve tanto al ALMACÉN
CENTRAL como a los ESTABLECIMIENTOS con SISMED propio (mismo formato, sacado del
FoxPro del puesto). El ORIGEN se resuelve por el ALMCOD:

    ALMCOD que empieza con el patrón del almacén ('034S…')  → ALMACEN
    ALMCOD cuyos 5 primeros dígitos cruzan con un cod_2000  → EESS_LOTE
        (código del establecimiento embebido; ej. '05552F0101' → 05552 → 00005552)

Es la MISMA lógica de parseo (consolidar lotes, negativos tal cual, fecha más
temprana ante inconsistencia); solo cambia cómo se resuelve la ubicación.

El stock por lote de un establecimiento SOLO alimenta Vencimientos y negativos
por lote — NO toca el CPMA / disponibilidad / situación (eso sigue saliendo del
ICI). Por eso solo el stock del ALMACÉN dispara recálculo.

ALMCOD identifica el almacén ('034S0501' = central) — es una entidad aparte, no
una FK. MEDCOD ya es consistente en 5 dígitos, no necesita normalización; si no
existe en el catálogo no se auto-crea (este archivo no trae descripción). Se
ignoran las columnas de compras/logística (PROVRUC, N_PEDIDO, COD_SIGA, etc.).

Un mismo (ubicación, producto, lote) puede venir partido en varias filas por
TIPSUM/FFINAN (o varios sub-almacenes del mismo puesto) — se consolidan sumando
`cantidad`. Si difieren en fecha_vcto o precio, se reporta incidencia y se usa la
fecha más temprana. Stock negativo real de SISMED se importa tal cual.

Es una FOTO del stock actual: cada importación reemplaza por completo el stock de
esa ubicación (por almacén, o por establecimiento — sin tocar a los demás).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.etl.dbf_reader import leer_dbf
from app.etl.numeric import a_decimal
from app.models.establecimiento import Establecimiento
from app.models.importacion import Importacion, Incidencia
from app.models.producto import Producto
from app.models.stock_almacen import (
    ORIGEN_ALMACEN,
    ORIGEN_EESS_LOTE,
    Stock,
    StgStockAlmacen,
    StockFueraCatalogo,
)
from app.repositories.cpma_repository import recalcular_por_productos
from app.repositories.historial_stock_repository import actualizar_historial_negativos

ANCHO_COD_ESTABLECIMIENTO = 8


@dataclass
class Ubicacion:
    """Dónde vive un stock por lote: el almacén central o un establecimiento.
    Se resuelve por el ALMCOD (ver módulo)."""
    origen: str
    almacen_cod: str | None = None  # ALMACEN
    establecimiento_id: int | None = None  # EESS_LOTE
    establecimiento_cod: str | None = None  # cod_2000 (EESS_LOTE)
    establecimiento_nombre: str | None = None

    @property
    def es_almacen(self) -> bool:
        return self.origen == ORIGEN_ALMACEN

    @property
    def etiqueta(self) -> str:
        if self.es_almacen:
            return f"Almacén {self.almacen_cod}"
        return f"{self.establecimiento_nombre} ({self.establecimiento_cod})"


def clasificar_almcod(almcod: str, est_por_cod8: dict[str, Establecimiento]) -> Ubicacion:
    """Resuelve la ubicación de un ALMCOD. Si sus 5 primeros dígitos cruzan con
    un establecimiento (cod_2000 con zfill 8) → EESS_LOTE; si no → ALMACEN."""
    almcod = (almcod or "").strip()
    cod5 = almcod[:5]
    if cod5.isdigit():
        est = est_por_cod8.get(cod5.zfill(ANCHO_COD_ESTABLECIMIENTO))
        if est is not None:
            return Ubicacion(
                origen=ORIGEN_EESS_LOTE,
                establecimiento_id=est.id,
                establecimiento_cod=est.cod_2000,
                establecimiento_nombre=est.nombre,
            )
    return Ubicacion(origen=ORIGEN_ALMACEN, almacen_cod=almcod)


def describir_origen_stock(filas: list[dict], establecimientos: list[Establecimiento]) -> dict:
    """Para la previsualización: mira los ALMCOD del archivo y dice si es del
    almacén o de un establecimiento (y cuál). `establecimientos`: catálogo con
    cod_2000 para el cruce."""
    est_por_cod8 = {e.cod_2000: e for e in establecimientos}
    ubic_por_almcod: dict[str, Ubicacion] = {}
    for f in filas:
        a = (f.get("almcod") or "").strip()
        if a and a not in ubic_por_almcod:
            ubic_por_almcod[a] = clasificar_almcod(a, est_por_cod8)

    ubicaciones = list(ubic_por_almcod.values())
    origenes = {u.origen for u in ubicaciones}
    if origenes == {ORIGEN_EESS_LOTE}:
        ests = {u.establecimiento_cod: u for u in ubicaciones}
        if len(ests) == 1:
            u = next(iter(ests.values()))
            return {
                "origen": "EESS",
                "establecimiento_cod": u.establecimiento_cod,
                "establecimiento_nombre": u.establecimiento_nombre,
                "almacen_cod": None,
            }
        # Varios establecimientos en un mismo archivo (raro): se reporta mixto.
        return {"origen": "MIXTO", "establecimiento_cod": None, "establecimiento_nombre": None, "almacen_cod": None}
    if origenes == {ORIGEN_ALMACEN}:
        cods = {u.almacen_cod for u in ubicaciones}
        return {
            "origen": "ALMACEN",
            "establecimiento_cod": None,
            "establecimiento_nombre": None,
            "almacen_cod": next(iter(cods)) if len(cods) == 1 else None,
        }
    return {"origen": "MIXTO", "establecimiento_cod": None, "establecimiento_nombre": None, "almacen_cod": None}


def _siguiente_version(db: Session, ubicacion_cod: str, periodo: date) -> int:
    ultima = db.scalar(
        select(Importacion.version)
        .where(Importacion.establecimiento_cod == ubicacion_cod, Importacion.periodo == periodo)
        .order_by(Importacion.version.desc())
    )
    return (ultima or 0) + 1


@dataclass
class ResumenUbicacion:
    ubicacion: str  # etiqueta legible
    origen: str
    cod: str  # almacen_cod o cod_2000
    importacion_id: int | None = None
    filas_leidas: int = 0
    lotes_promovidos: int = 0  # lotes importados (producto en catálogo)
    lotes_fuera_catalogo: int = 0  # lotes NO importados (producto fuera del catálogo)
    incidencias: int = 0


@dataclass
class ResumenImportacionStock:
    archivo: str
    periodo: str
    ubicaciones: list[ResumenUbicacion] = field(default_factory=list)
    productos_afectados: set[int] = field(default_factory=set)
    calc_cpma_recalculados: int = 0
    calc_cpma_red_recalculados: int = 0

    def texto(self) -> str:
        partes = "; ".join(
            f"{u.ubicacion} [{u.origen}]: {u.filas_leidas} filas, {u.lotes_promovidos} lotes, "
            f"{u.lotes_fuera_catalogo} fuera de catálogo, {u.incidencias} incidencias"
            for u in self.ubicaciones
        )
        return (
            f"{self.archivo} ({self.periodo}): {partes}. "
            f"calc_cpma recalculado para {self.calc_cpma_recalculados} pares, "
            f"calc_cpma_red para {self.calc_cpma_red_recalculados} productos."
        )


def _registrar_incidencia(
    db: Session,
    resumen_ubic: ResumenUbicacion,
    importacion: Importacion,
    fila_id: int | None,
    tipo: str,
    detalle: str,
) -> None:
    db.add(
        Incidencia(
            importacion_id=importacion.id,
            tabla_origen="stg_stock_almacen",
            fila_id=fila_id,
            tipo=tipo,
            detalle=detalle,
        )
    )
    resumen_ubic.incidencias += 1
    importacion.incidencias = (importacion.incidencias or 0) + 1


def importar_stock_almacen(
    db: Session,
    ruta_dbf: str | Path,
    periodo: date,
    usuario: str | None = None,
    recalcular: bool = True,
) -> ResumenImportacionStock:
    """El archivo puede traer el almacén y/o un establecimiento (por su ALMCOD);
    cada ubicación es una importación independiente que reemplaza por completo su
    stock por lote anterior, sin tocar a las demás."""
    ruta_dbf = Path(ruta_dbf)
    resumen = ResumenImportacionStock(archivo=ruta_dbf.name, periodo=periodo.strftime("%Y%m"))

    filas = leer_dbf(ruta_dbf)

    establecimientos = db.scalars(
        select(Establecimiento).where(Establecimiento.es_almacen.is_(False))
    ).all()
    est_por_cod8 = {e.cod_2000: e for e in establecimientos}

    # Resuelve la ubicación de cada ALMCOD y agrupa las filas por ubicación.
    # Para EESS varios ALMCOD del mismo puesto (F0101, F0102…) colapsan en uno.
    ubic_por_almcod: dict[str, Ubicacion] = {}
    almcods_por_clave: dict[object, set[str]] = defaultdict(set)
    filas_por_clave: dict[object, list[dict]] = defaultdict(list)

    def clave_de(u: Ubicacion) -> object:
        return ("A", u.almacen_cod) if u.es_almacen else ("E", u.establecimiento_id)

    for fila in filas:
        almcod = (fila.get("almcod") or "").strip()
        u = ubic_por_almcod.get(almcod)
        if u is None:
            u = clasificar_almcod(almcod, est_por_cod8)
            ubic_por_almcod[almcod] = u
        clave = clave_de(u)
        almcods_por_clave[clave].add(almcod)
        filas_por_clave[clave].append(fila)

    productos = {p.medcod: p.id for p in db.scalars(select(Producto))}
    medcod_por_id = {pid: mc for mc, pid in productos.items()}
    ahora = datetime.now()  # marca de tiempo de esta carga (la foto es intradía)

    for clave, filas_ubic in filas_por_clave.items():
        # Ubicación representativa (todas las de la misma clave comparten origen).
        almcods = sorted(almcods_por_clave[clave])
        ubicacion = ubic_por_almcod[almcods[0]]

        # Código con que se registra la importación: para EESS un ALMCOD real (no
        # el cod_2000) para no confundir a "pendientes" (que cuenta ICI por cod).
        importacion_cod = ubicacion.almacen_cod if ubicacion.es_almacen else almcods[0]

        resumen_ubic = ResumenUbicacion(
            ubicacion=ubicacion.etiqueta,
            origen=ubicacion.origen,
            cod=ubicacion.almacen_cod if ubicacion.es_almacen else ubicacion.establecimiento_cod,
            filas_leidas=len(filas_ubic),
        )
        resumen.ubicaciones.append(resumen_ubic)

        importacion = Importacion(
            archivo=ruta_dbf.name,
            establecimiento_cod=importacion_cod,
            periodo=periodo,
            version=_siguiente_version(db, importacion_cod, periodo),
            estado="PROCESANDO",
            usuario=usuario,
        )
        db.add(importacion)
        db.flush()
        resumen_ubic.importacion_id = importacion.id

        stg_rows = [
            StgStockAlmacen(
                importacion_id=importacion.id,
                almcod=fila.get("almcod"),
                medcod=fila.get("medcod"),
                medlote=fila.get("medlote"),
                medfechvto=fila.get("medfechvto").isoformat() if fila.get("medfechvto") else None,
                stksaldode=fila.get("stksaldode"),
                stkprecio=fila.get("stkprecio"),
                medregsan=fila.get("medregsan"),
            )
            for fila in filas_ubic
        ]
        db.add_all(stg_rows)
        db.flush()

        # El almacén consolida por (producto, lote). El stock por lote de un
        # establecimiento agrupa ADEMÁS por fecha de vencimiento: en SISMED un
        # mismo código de lote puede traer vencimientos distintos (son lotes
        # físicamente distintos) y fundirlos fecharía stock bueno como vencido.
        grupos: dict[tuple, list[StgStockAlmacen]] = defaultdict(list)
        for stg in stg_rows:
            clave = ((stg.medcod or "").strip(), (stg.medlote or "").strip())
            if not ubicacion.es_almacen:
                clave = clave + ((stg.medfechvto or "").strip(),)
            grupos[clave].append(stg)

        filas_nuevas = []
        filas_fuera = []  # lotes de productos fuera del catálogo del almacén
        for stg_grupo in grupos.values():
            primero = stg_grupo[0]
            medcod = (primero.medcod or "").strip()
            medlote = (primero.medlote or "").strip()

            if not medlote:
                for stg in stg_grupo:
                    _registrar_incidencia(
                        db, resumen_ubic, importacion, stg.id, "LOTE_VACIO",
                        f"MEDLOTE vacío para MEDCOD {medcod!r}",
                    )
                continue

            # Consolida la cantidad del grupo (mismo lote partido en varias filas).
            cantidad_total = Decimal(0)
            campo_malo = None
            for stg in stg_grupo:
                cantidad = a_decimal(stg.stksaldode)
                precio = a_decimal(stg.stkprecio)
                if cantidad is None or precio is None:
                    campo_malo = stg
                    break
                cantidad_total += cantidad

            if campo_malo is not None:
                _registrar_incidencia(
                    db, resumen_ubic, importacion, campo_malo.id, "CANTIDAD_NO_NUMERICA",
                    f"STKSALDODE={campo_malo.stksaldode!r} o STKPRECIO={campo_malo.stkprecio!r} "
                    f"inválido para MEDCOD {medcod!r}, lote {medlote!r}",
                )
                continue

            fechas = {stg.medfechvto for stg in stg_grupo if stg.medfechvto}
            fecha_vcto = min(fechas) if fechas else None
            reg_sanitario = next(
                (s.medregsan.strip() for s in stg_grupo if s.medregsan and s.medregsan.strip()),
                None,
            )

            prod_id = productos.get(medcod)
            if prod_id is None:
                # Fuera del catálogo del almacén: el catálogo es único y oficial;
                # NO se crea el producto. El puesto lo maneja por vía externa
                # (DIRESA/CENARES/donación). Se reporta como dato a revisar.
                _registrar_incidencia(
                    db, resumen_ubic, importacion, primero.id, "PRODUCTO_FUERA_CATALOGO",
                    f"Producto {medcod} fuera del catálogo del almacén "
                    f"(lote {medlote}, saldo {cantidad_total}, vence {fecha_vcto or 's/f'}). "
                    f"El puesto lo maneja por vía externa (DIRESA/CENARES/donación); "
                    f"no se agrega al catálogo central.",
                )
                filas_fuera.append({
                    "origen": ubicacion.origen,
                    "almacen_cod": ubicacion.almacen_cod,
                    "establecimiento_id": ubicacion.establecimiento_id,
                    "medcod": medcod,
                    "lote": medlote,
                    "fecha_vcto": date.fromisoformat(fecha_vcto) if fecha_vcto else None,
                    "cantidad": cantidad_total,
                    "precio": a_decimal(primero.stkprecio),
                    "reg_sanitario": reg_sanitario,
                    "periodo": periodo,
                    "importacion_id": importacion.id,
                })
                continue

            # Producto en catálogo: se importa al stock por lote.
            if len(fechas) > 1:
                _registrar_incidencia(
                    db, resumen_ubic, importacion, primero.id, "LOTE_FECHA_INCONSISTENTE",
                    f"MEDCOD {medcod!r}, lote {medlote!r}: fechas de vencimiento distintas "
                    f"entre filas del mismo lote ({sorted(fechas)}); se usó la más temprana.",
                )

            precios = {a_decimal(stg.stkprecio) for stg in stg_grupo}
            if len(precios) > 1:
                _registrar_incidencia(
                    db, resumen_ubic, importacion, primero.id, "LOTE_PRECIO_INCONSISTENTE",
                    f"MEDCOD {medcod!r}, lote {medlote!r}: precios distintos entre filas del "
                    f"mismo lote ({sorted(precios)}); se usó {a_decimal(primero.stkprecio)}.",
                )

            if cantidad_total < 0:
                _registrar_incidencia(
                    db, resumen_ubic, importacion, primero.id, "CANTIDAD_NEGATIVA",
                    f"MEDCOD {medcod!r}, lote {medlote!r}: stock negativo real de SISMED "
                    f"({cantidad_total}) — se importa tal cual, no se fuerza a 0",
                )

            filas_nuevas.append({
                "origen": ubicacion.origen,
                "almacen_cod": ubicacion.almacen_cod,
                "establecimiento_id": ubicacion.establecimiento_id,
                "producto_id": prod_id,
                "lote": medlote,
                "fecha_vcto": date.fromisoformat(fecha_vcto) if fecha_vcto else None,
                "cantidad": cantidad_total,
                "precio": a_decimal(primero.stkprecio),
                "reg_sanitario": reg_sanitario,
                "periodo": periodo,
                "importacion_id": importacion.id,
            })
            # El stock por lote de un EESS NO alimenta el CPMA; solo el del almacén.
            if ubicacion.es_almacen:
                resumen.productos_afectados.add(prod_id)

        # Reemplaza por completo el stock por lote de ESTA ubicación (foto actual),
        # sin tocar el almacén ni a otros puestos. Igual para el reporte de fuera
        # de catálogo (misma ubicación).
        if ubicacion.es_almacen:
            db.execute(
                delete(Stock).where(
                    Stock.origen == ORIGEN_ALMACEN, Stock.almacen_cod == ubicacion.almacen_cod
                )
            )
            db.execute(
                delete(StockFueraCatalogo).where(
                    StockFueraCatalogo.origen == ORIGEN_ALMACEN,
                    StockFueraCatalogo.almacen_cod == ubicacion.almacen_cod,
                )
            )
        else:
            db.execute(
                delete(Stock).where(
                    Stock.origen == ORIGEN_EESS_LOTE,
                    Stock.establecimiento_id == ubicacion.establecimiento_id,
                )
            )
            db.execute(
                delete(StockFueraCatalogo).where(
                    StockFueraCatalogo.origen == ORIGEN_EESS_LOTE,
                    StockFueraCatalogo.establecimiento_id == ubicacion.establecimiento_id,
                )
            )
        if filas_nuevas:
            db.add_all(Stock(**f) for f in filas_nuevas)
        if filas_fuera:
            db.add_all(StockFueraCatalogo(**f) for f in filas_fuera)

        # Historial de negativos: compara esta foto contra las incidencias abiertas
        # de esta ubicación (detecta resueltos solos). Tablas aparte del stock.
        actualizar_historial_negativos(
            db,
            origen=ubicacion.origen,
            almacen_cod=ubicacion.almacen_cod,
            establecimiento_id=ubicacion.establecimiento_id,
            filas_nuevas=filas_nuevas,
            medcod_por_id=medcod_por_id,
            importacion_id=importacion.id,
            ahora=ahora,
        )

        resumen_ubic.lotes_promovidos = len(filas_nuevas)
        resumen_ubic.lotes_fuera_catalogo = len(filas_fuera)
        importacion.filas_detalle = len(stg_rows)
        importacion.estado = "OK"

    db.commit()

    # En un lote unificado el CPMA se recalcula una sola vez al final (lo hace el
    # orquestador), no por archivo — por eso `recalcular` puede ser False. Solo el
    # stock del almacén afecta la disponibilidad (productos_afectados solo lo tiene él).
    if recalcular and resumen.productos_afectados:
        n_est, n_red = recalcular_por_productos(db, resumen.productos_afectados)
        db.commit()
        resumen.calc_cpma_recalculados = n_est
        resumen.calc_cpma_red_recalculados = n_red

    return resumen


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Importa el stock por lote (MSTKALMDE.DBF).")
    parser.add_argument("ruta_dbf", type=Path, help="Ruta al archivo .dbf")
    parser.add_argument("--periodo", required=True, help="Mes de la foto de stock, formato AAAA-MM")
    parser.add_argument("--usuario", default=None)
    args = parser.parse_args()

    anio, mes = (int(x) for x in args.periodo.split("-"))
    periodo = date(anio, mes, 1)

    db = SessionLocal()
    try:
        resumen = importar_stock_almacen(db, args.ruta_dbf, periodo, usuario=args.usuario)
    finally:
        db.close()

    print(resumen.texto())


if __name__ == "__main__":
    main()
