"""
Importador del ICI (Informe de Consumo Integrado) — un .dbf por
establecimiento, una fila por producto (CODIGO_MED, MES01..MES12,
STOCK, PRECIO, CPA/SITUACION de referencia). CODIGO_PRE llega vacío, así
que `establecimiento_cod` y `periodo` son parámetros obligatorios.

MES01..MES12 no traen año: se asume MES12 = periodo de cierre, MES01 =
11 meses atrás (pendiente de confirmar con el doc).

Flujo: staging (texto crudo) → validar (número, producto en catálogo)
→ promover (upsert en `ici`, 12 filas por producto) → comparar nuestro
CPMA recalculado contra el CPA de SISMED (solo referencia, no se usa
para calcular).
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.etl.dbf_reader import leer_dbf
from app.etl.deteccion import coincide_nombre
from app.etl.numeric import a_decimal
from app.models.establecimiento import Establecimiento
from app.models.ici import Ici, StgIci
from app.models.importacion import Importacion, Incidencia
from app.models.producto import Producto
from app.models.stock_almacen import ORIGEN_EESS, Stock
from app.services.cpma import calcular_cpma

CAMPOS_MES = tuple(f"mes{n:02d}" for n in range(1, 13))

# Diferencia máxima aceptable entre nuestro CPMA y el CPA de SISMED antes de incidencia.
UMBRAL_DIFERENCIA_CPA = Decimal(1)

# CODIGO_PRE (5 dígitos) y cod_2000 (8 dígitos) son el mismo código con distinto relleno.
ANCHO_COD_ESTABLECIMIENTO = 8


def _normalizar_codigo_establecimiento(codigo: str | None) -> str | None:
    texto = (codigo or "").strip()
    if not texto:
        return None
    return texto.zfill(ANCHO_COD_ESTABLECIMIENTO)


def _ventana_12_meses(periodo: date) -> list[tuple[int, int]]:
    """12 (año, mes) calendario terminando en `periodo`, orden MES01..MES12."""
    base = periodo.year * 12 + (periodo.month - 1)
    return [((base - i) // 12, (base - i) % 12 + 1) for i in range(11, -1, -1)]


@dataclass
class ResumenImportacionICI:
    archivo: str
    importacion_id: int | None = None
    establecimiento: str | None = None
    periodo: str | None = None
    filas_leidas: int = 0
    filas_staging: int = 0
    productos_promovidos: int = 0
    productos_creados: int = 0
    productos_cpma_calza: int = 0
    incidencias: int = 0
    pares_afectados: set[tuple[int, int]] = field(default_factory=set)

    def texto(self) -> str:
        return (
            f"{self.archivo}: {self.filas_leidas} productos ({self.establecimiento}, "
            f"{self.periodo}), {self.incidencias} incidencias, "
            f"{self.productos_promovidos} promovidos, {self.productos_creados} creados, "
            f"{self.productos_cpma_calza}/{self.productos_promovidos} calzan con CPA de SISMED."
        )


def _siguiente_version(db: Session, establecimiento_cod: str, periodo: date) -> int:
    ultima = db.scalar(
        select(Importacion.version)
        .where(Importacion.establecimiento_cod == establecimiento_cod, Importacion.periodo == periodo)
        .order_by(Importacion.version.desc())
    )
    return (ultima or 0) + 1


def _registrar_incidencia(
    db: Session,
    resumen: ResumenImportacionICI,
    importacion: Importacion,
    fila_id: int | None,
    tipo: str,
    detalle: str,
) -> None:
    db.add(
        Incidencia(
            importacion_id=importacion.id,
            tabla_origen="stg_ici",
            fila_id=fila_id,
            tipo=tipo,
            detalle=detalle,
        )
    )
    resumen.incidencias += 1
    importacion.incidencias = (importacion.incidencias or 0) + 1


_COLUMNAS_FIJAS = ("consumo", "precio", "importacion_id")
_COLUMNAS_COALESCE = ("stock_final", "cpa_sismed", "situacion_sismed")


def _guardar_ici(db: Session, filas_upsert: list[dict]) -> None:
    """COALESCE en columnas que solo se conocen en el mes de cierre: al
    reimportar el mes siguiente, ese mismo mes vuelve como histórico
    (sin esos valores) y no debe pisar lo ya guardado con NULL."""
    stmt = mysql_insert(Ici).values(filas_upsert)
    actualizables = {col: stmt.inserted[col] for col in _COLUMNAS_FIJAS}
    for col in _COLUMNAS_COALESCE:
        actualizables[col] = func.coalesce(stmt.inserted[col], getattr(Ici, col))
    stmt = stmt.on_duplicate_key_update(**actualizables)
    db.execute(stmt)


def importar_ici(
    db: Session,
    ruta_dbf: str | Path,
    establecimiento_cod: str,
    periodo: date,
    usuario: str | None = None,
) -> ResumenImportacionICI:
    ruta_dbf = Path(ruta_dbf)
    codigo_norm = _normalizar_codigo_establecimiento(establecimiento_cod)
    if codigo_norm is None:
        raise ValueError(f"establecimiento_cod vacío o inválido: {establecimiento_cod!r}")

    establecimiento = db.scalar(select(Establecimiento).where(Establecimiento.cod_2000 == codigo_norm))
    if establecimiento is None:
        raise ValueError(f"No existe establecimiento con cod_2000={codigo_norm!r}")

    resumen = ResumenImportacionICI(
        archivo=ruta_dbf.name, establecimiento=codigo_norm, periodo=periodo.strftime("%Y%m")
    )

    filas = leer_dbf(ruta_dbf)
    resumen.filas_leidas = len(filas)

    importacion = Importacion(
        archivo=ruta_dbf.name,
        establecimiento_cod=codigo_norm,
        periodo=periodo,
        version=_siguiente_version(db, codigo_norm, periodo),
        estado="PROCESANDO",
        usuario=usuario,
    )
    db.add(importacion)
    db.flush()
    resumen.importacion_id = importacion.id

    if not coincide_nombre(ruta_dbf.name, establecimiento.nombre):
        _registrar_incidencia(
            db, resumen, importacion, None, "ESTABLECIMIENTO_NO_COINCIDE_ARCHIVO",
            f"El nombre del archivo {ruta_dbf.name!r} no parece corresponder a "
            f"{establecimiento.nombre!r} (cod_2000={codigo_norm}). Se importó igual "
            f"porque el código fue explícito, pero conviene confirmarlo.",
        )

    stg_rows = [
        StgIci(
            importacion_id=importacion.id,
            codigo_med=fila.get("codigo_med"),
            descrip=fila.get("descrip"),
            medtip=fila.get("medtip"),
            medpet=fila.get("medpet"),
            medest=fila.get("medest"),
            ff=fila.get("ff"),
            **{campo: fila.get(campo) for campo in CAMPOS_MES},
            stock=fila.get("stock"),
            precio=fila.get("precio"),
            cpa=fila.get("cpa"),
            situacion=fila.get("situacion"),
        )
        for fila in filas
    ]
    db.add_all(stg_rows)
    db.flush()
    resumen.filas_staging = len(stg_rows)

    productos = {p.medcod: p for p in db.scalars(select(Producto))}
    ventana = _ventana_12_meses(periodo)

    filas_upsert = []
    # Stock EESS del cierre (por producto, sin lote) para la tabla `stock` unificada.
    stock_eess: list[tuple[int, Decimal]] = []
    for stg in stg_rows:
        codigo_med = (stg.codigo_med or "").strip()
        descrip = (stg.descrip or "").strip()

        # Clasificación del producto (códigos crudos del ICI, tal cual el doc):
        # MEDTIP=M/I, MEDPET=P/_, MEDEST=E/S/_, FF=forma farmacéutica.
        medtip = (stg.medtip or "").strip().upper() or None
        medpet = (stg.medpet or "").strip() or None
        medest = (stg.medest or "").strip().upper() or None
        ff = (stg.ff or "").strip() or None
        es_petitorio = (medpet or "").upper() == "P"

        producto = productos.get(codigo_med)
        if producto is None:
            if not codigo_med or not descrip:
                _registrar_incidencia(
                    db, resumen, importacion, stg.id, "PRODUCTO_INEXISTENTE",
                    f"CODIGO_MED {codigo_med!r} no existe en mproducto y no se puede "
                    f"crear (CODIGO_MED o DESCRIP vacío)",
                )
                continue
            producto = Producto(
                medcod=codigo_med,
                nombre=descrip,
                tipo=medtip,
                medpet=medpet,
                medest=medest,
                forma_farma=ff,
                es_petitorio=es_petitorio,
                origen="ICI",  # aún no visto en el catálogo oficial (MPRODUCTO)
            )
            db.add(producto)
            db.flush()
            productos[codigo_med] = producto
            resumen.productos_creados += 1
        else:
            # Refresca la clasificación en cada carga, sin pisar con vacío
            # (esos campos pueden confirmarse/corregirse en cargas posteriores).
            if medtip is not None:
                producto.tipo = medtip
            if medpet is not None:
                producto.medpet = medpet
                producto.es_petitorio = es_petitorio
            if medest is not None:
                producto.medest = medest
            if ff is not None:
                producto.forma_farma = ff

        prod_id = producto.id

        consumos: list[Decimal] = []
        campo_malo = None
        for campo in CAMPOS_MES:
            dec = a_decimal(getattr(stg, campo))
            if dec is None:
                campo_malo = campo
                break
            consumos.append(dec)

        stock_dec = a_decimal(stg.stock)
        precio_dec = a_decimal(stg.precio)
        cpa_dec = a_decimal(stg.cpa)
        if campo_malo is None and (stock_dec is None or precio_dec is None or cpa_dec is None):
            campo_malo = "stock/precio/cpa"

        if campo_malo is not None:
            _registrar_incidencia(
                db, resumen, importacion, stg.id, "CANTIDAD_NO_NUMERICA",
                f"{campo_malo} inválido para producto {codigo_med} ({stg.descrip})",
            )
            continue

        _, _, cpma = calcular_cpma(consumos)
        diferencia_cpa = abs(cpma - cpa_dec)
        if diferencia_cpa <= UMBRAL_DIFERENCIA_CPA:
            resumen.productos_cpma_calza += 1
        else:
            _registrar_incidencia(
                db, resumen, importacion, stg.id, "CPMA_DIFIERE_SISMED",
                f"producto {codigo_med} ({stg.descrip}): nuestro CPMA={cpma} "
                f"vs CPA de SISMED={cpa_dec} (diferencia={diferencia_cpa})",
            )

        for i, (anio, mes) in enumerate(ventana):
            es_cierre = (anio, mes) == (periodo.year, periodo.month)
            filas_upsert.append({
                "establecimiento_id": establecimiento.id,
                "producto_id": prod_id,
                "anio": anio,
                "mes": mes,
                "consumo": consumos[i],
                "stock_final": stock_dec if es_cierre else None,
                "precio": precio_dec,
                "cpa_sismed": cpa_dec if es_cierre else None,
                "situacion_sismed": (stg.situacion.strip() or None) if es_cierre and stg.situacion else None,
                "importacion_id": importacion.id,
            })

        resumen.pares_afectados.add((establecimiento.id, prod_id))
        resumen.productos_promovidos += 1
        stock_eess.append((prod_id, stock_dec))

    if filas_upsert:
        _guardar_ici(db, filas_upsert)

    # Stock EESS unificado: reemplaza por completo la foto de este establecimiento
    # (por producto, sin lote — el ICI no trae lote). Alimenta el módulo de Stock
    # y la detección de negativos, junto al stock del almacén, en una sola tabla.
    db.execute(
        delete(Stock).where(Stock.origen == ORIGEN_EESS, Stock.establecimiento_id == establecimiento.id)
    )
    if stock_eess:
        db.add_all(
            Stock(
                origen=ORIGEN_EESS,
                establecimiento_id=establecimiento.id,
                producto_id=prod_id,
                cantidad=cantidad,
                periodo=periodo,
                importacion_id=importacion.id,
            )
            for prod_id, cantidad in stock_eess
        )

    importacion.filas_detalle = len(stg_rows)
    importacion.estado = "OK"
    db.commit()
    return resumen


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Importa el .dbf del ICI de un establecimiento.")
    parser.add_argument("ruta_dbf", type=Path, help="Ruta al archivo .dbf del establecimiento")
    parser.add_argument("--establecimiento", required=True, help="cod_2000 del establecimiento")
    parser.add_argument("--periodo", required=True, help="Mes de cierre, formato AAAA-MM")
    parser.add_argument("--usuario", default=None, help="Usuario que ejecuta la importación")
    args = parser.parse_args()

    anio, mes = (int(x) for x in args.periodo.split("-"))
    periodo = date(anio, mes, 1)

    db = SessionLocal()
    try:
        resumen = importar_ici(db, args.ruta_dbf, args.establecimiento, periodo, usuario=args.usuario)
    finally:
        db.close()

    print(resumen.texto())
    if resumen.incidencias:
        print(f"Ver tabla `incidencia` filtrando por importacion_id = {resumen.importacion_id}")


if __name__ == "__main__":
    main()
