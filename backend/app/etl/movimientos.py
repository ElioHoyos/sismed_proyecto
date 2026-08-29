"""
Importador de MOVIMIENTOS de kardex: TMOVIM (cabecera) + TMOVIMDET (detalle),
unidos por MOVCODITIP + MOVNUMERO. Encoding cp850.

PRIVACIDAD — CRÍTICO: los DBF traen datos personales de pacientes. Este
importador SOLO lee las columnas permitidas (producto y movimiento) y NUNCA
persiste ni registra ninguna columna de paciente: MOVREFE textual con nombres,
DNI_CLIE, DIAGCOD/DIAGCOD1/DIAGCOD2, PCTCOD, PERCOD, CLICOD. De MOVREFE solo se
deriva una categoría genérica (SIS/GENERAL/INTERV. SANITARIA/NOMINAL); el texto
original jamás se guarda.

Establecimiento: los ALMCOD (ORG/DST) traen el código del puesto embebido en sus
5 primeros dígitos (05552 → cod_2000 00005552). Para salidas viene en ORG; para
entradas, en DST. Se resuelve el que cruce con un establecimiento (no almacén).

Idempotencia: reimportar reemplaza el histórico de movimientos de ese puesto.
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from dbfread import DBF
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.establecimiento import Establecimiento
from app.models.importacion import Importacion
from app.models.movimiento import CAT_GENERAL, CAT_INTERV, CAT_NOMINAL, CAT_SIS, Movimiento
from app.models.producto import Producto

ANCHO_COD = 8
_CHUNK = 5000  # filas por lote de INSERT (multi-fila) para la carga masiva

# Orden fijo de columnas para el INSERT masivo (executemany con %s posicional).
_COLS_INS = (
    "establecimiento_id", "producto_id", "tipo", "numero", "item", "fecha_emision",
    "fecha_registro", "lote", "fecha_vcto", "cantidad", "precio", "total",
    "tipsum", "ffinan", "categoria", "importacion_id",
)

# Columnas que SÍ se leen (todo lo demás —paciente incluido— se ignora).
_COLS_CAB = ("movcoditip", "movnumero", "almcodiorg", "almcodidst", "movfechemi", "movfechreg", "movrefe")
_COLS_DET = ("movcoditip", "movnumero", "movnumeite", "medcod", "medlote", "medfechvto",
             "movcantid", "movprecio", "movtotal", "tipsum", "ffinan")


def _categoria(movrefe: str | None) -> str:
    """Categoría genérica de una salida a partir de MOVREFE — SIN guardar el
    texto (que en las nominales es el nombre del paciente)."""
    r = (movrefe or "").upper()
    if "SIS" in r:
        return CAT_SIS
    if "INTERV" in r:
        return CAT_INTERV
    if "GENERAL" in r:
        return CAT_GENERAL
    return CAT_NOMINAL


def _iter_permitido(ruta: Path, columnas: tuple[str, ...]):
    """Itera un DBF cp850 devolviendo SOLO las columnas permitidas (las de
    paciente ni se retienen)."""
    tabla = DBF(str(ruta), encoding="cp850", lowernames=True, char_decode_errors="ignore")
    for rec in tabla:
        yield {c: rec.get(c) for c in columnas}


def _texto(v) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t or None


def _dt(v):
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    return None


@dataclass
class ResumenMovim:
    archivo: str
    establecimiento_cod: str | None = None
    establecimiento_nombre: str | None = None
    importacion_id: int | None = None
    cabeceras: int = 0
    lineas_leidas: int = 0
    movimientos: int = 0
    fuera_catalogo: int = 0  # líneas con MEDCOD no en catálogo (se omiten)
    huerfanas: int = 0  # líneas de detalle sin cabecera (se omiten)
    por_categoria: dict = field(default_factory=dict)

    def texto(self) -> str:
        cat = ", ".join(f"{k}: {v}" for k, v in sorted(self.por_categoria.items()))
        return (
            f"{self.archivo}: {self.establecimiento_nombre} ({self.establecimiento_cod}) — "
            f"{self.movimientos} movimientos de {self.lineas_leidas} líneas "
            f"({self.fuera_catalogo} fuera de catálogo, {self.huerfanas} sin cabecera). "
            f"Salidas por categoría: {cat}."
        )


def _resolver_est(cod5: str, est_por_cod8: dict[str, Establecimiento]) -> Establecimiento | None:
    if cod5.isdigit():
        return est_por_cod8.get(cod5.zfill(ANCHO_COD))
    return None


def describir_establecimiento_movim(ruta_cab: Path, establecimientos: list[Establecimiento]) -> dict:
    """Para la previsualización: resuelve a qué puesto pertenece el TMOVIM por
    sus ALMCOD (ORG/DST). Devuelve {establecimiento_cod, establecimiento_nombre}."""
    est_por_cod8 = {e.cod_2000: e for e in establecimientos}
    visto: Counter = Counter()
    for fila in _iter_permitido(ruta_cab, ("almcodiorg", "almcodidst")):
        for campo in ("almcodiorg", "almcodidst"):
            est = _resolver_est((fila.get(campo) or "")[:5], est_por_cod8)
            if est is not None:
                visto[est.cod_2000] += 1
    if not visto:
        return {"establecimiento_cod": None, "establecimiento_nombre": None}
    cod = visto.most_common(1)[0][0]
    return {"establecimiento_cod": cod, "establecimiento_nombre": est_por_cod8[cod].nombre}


def contar_lineas_movim(ruta_det: Path) -> int:
    """Cuenta líneas del detalle (para la previsualización)."""
    return sum(1 for _ in _iter_permitido(ruta_det, ("movnumero",)))


def importar_movimientos(
    db: Session,
    ruta_cab: str | Path,
    ruta_det: str | Path,
    usuario: str | None = None,
) -> ResumenMovim:
    ruta_cab, ruta_det = Path(ruta_cab), Path(ruta_det)
    resumen = ResumenMovim(archivo=ruta_det.name)

    establecimientos = db.scalars(
        select(Establecimiento).where(Establecimiento.es_almacen.is_(False))
    ).all()
    est_por_cod8 = {e.cod_2000: e for e in establecimientos}

    # 1) Cabecera → mapa (tipo, numero) → {fecha, categoría, establecimiento}.
    #    Solo columnas permitidas; MOVREFE se usa y se descarta (categoría).
    cab: dict[tuple[str, str], dict] = {}
    ests_vistos: set[int] = set()
    por_cat: Counter = Counter()
    for r in _iter_permitido(ruta_cab, _COLS_CAB):
        tipo = (r.get("movcoditip") or "").strip()
        numero = (r.get("movnumero") or "").strip()
        if not numero:
            continue
        est = _resolver_est((r.get("almcodiorg") or "")[:5], est_por_cod8) or _resolver_est(
            (r.get("almcodidst") or "")[:5], est_por_cod8
        )
        if est is None:
            continue
        categoria = _categoria(r.get("movrefe")) if tipo == "S" else None
        if categoria:
            por_cat[categoria] += 1
        # MOVFECHEMI suele venir vacío en estos archivos; la fecha efectiva del
        # movimiento es la de registro (MOVFECHREG). Se usa como respaldo.
        cab[(tipo, numero)] = {
            "establecimiento_id": est.id,
            "fecha_emision": _dt(r.get("movfechemi")) or _dt(r.get("movfechreg")),
            "fecha_registro": _dt(r.get("movfechreg")),
            "categoria": categoria,
        }
        ests_vistos.add(est.id)
    resumen.cabeceras = len(cab)
    resumen.por_categoria = dict(por_cat)

    if ests_vistos:
        cod = next(iter(ests_vistos))
        e = db.get(Establecimiento, cod)
        resumen.establecimiento_cod = e.cod_2000 if e else None
        resumen.establecimiento_nombre = e.nombre if e else None

    # Importación (con cod prefijado para no confundir a "pendientes" de ICI).
    importacion = Importacion(
        archivo=ruta_det.name,
        establecimiento_cod=f"MOVIM-{resumen.establecimiento_cod or '?'}",
        periodo=None,
        version=1,
        estado="PROCESANDO",
        usuario=usuario,
    )
    db.add(importacion)
    db.flush()
    resumen.importacion_id = importacion.id

    productos = {p.medcod: p.id for p in db.scalars(select(Producto))}

    # 2) Detalle → filas de movimiento (join por (tipo, numero)); PII nunca entra.
    filas: list[dict] = []
    for r in _iter_permitido(ruta_det, _COLS_DET):
        resumen.lineas_leidas += 1
        tipo = (r.get("movcoditip") or "").strip()
        numero = (r.get("movnumero") or "").strip()
        h = cab.get((tipo, numero))
        if h is None:
            resumen.huerfanas += 1
            continue
        medcod = (r.get("medcod") or "").strip()
        prod_id = productos.get(medcod)
        if prod_id is None:
            resumen.fuera_catalogo += 1
            continue
        filas.append({
            "establecimiento_id": h["establecimiento_id"],
            "producto_id": prod_id,
            "tipo": tipo,
            "numero": numero,
            "item": _texto(r.get("movnumeite")),
            "fecha_emision": h["fecha_emision"],
            "fecha_registro": h["fecha_registro"],
            "lote": _texto(r.get("medlote")),
            "fecha_vcto": r.get("medfechvto") if isinstance(r.get("medfechvto"), date) else None,
            "cantidad": r.get("movcantid") or 0,
            "precio": r.get("movprecio"),
            "total": r.get("movtotal"),
            "tipsum": _texto(r.get("tipsum")),
            "ffinan": _texto(r.get("ffinan")),
            "categoria": h["categoria"],
            "importacion_id": importacion.id,
        })

    # Idempotencia: reemplaza el histórico de movimientos de este/estos puesto(s).
    if ests_vistos:
        db.execute(delete(Movimiento).where(Movimiento.establecimiento_id.in_(ests_vistos)))

    # Carga masiva: INSERT multi-fila (executemany) con los chequeos de FK/unique
    # apagados durante la carga (ya validamos producto_id en catálogo). El chequeo
    # de FK por fila era el cuello real con decenas de miles de líneas.
    if filas:
        sql = (
            f"INSERT INTO movimiento ({', '.join(_COLS_INS)}) "
            f"VALUES ({', '.join(['%s'] * len(_COLS_INS))})"
        )
        raw = db.connection().connection
        cur = raw.cursor()
        cur.execute("SET SESSION foreign_key_checks=0")
        cur.execute("SET SESSION unique_checks=0")
        try:
            for i in range(0, len(filas), _CHUNK):
                cur.executemany(sql, [tuple(f[c] for c in _COLS_INS) for f in filas[i:i + _CHUNK]])
        finally:
            cur.execute("SET SESSION foreign_key_checks=1")
            cur.execute("SET SESSION unique_checks=1")
    resumen.movimientos = len(filas)

    importacion.filas_detalle = resumen.lineas_leidas
    importacion.estado = "OK"
    db.commit()
    return resumen


def main() -> None:
    import sys

    cab, det = Path(sys.argv[1]), Path(sys.argv[2])
    db = SessionLocal()
    try:
        r = importar_movimientos(db, cab, det)
    finally:
        db.close()
    print(r.texto())


if __name__ == "__main__":
    main()
