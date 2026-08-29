"""Carga unificada de DBF: el usuario sube archivos (sueltos o un ZIP mezclado)
sin saber a qué importador van; el sistema detecta el tipo por columnas
(ICI / stock de almacén / catálogo), lo confirma en la previsualización, y al
importar enruta cada uno a su importador (CPMA recalculado una sola vez al
final). Ver app/etl/carga_lote.py y app/etl/deteccion_tipo.py."""
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_db
from app.etl.carga import ArchivoNoSoportado, materializar_dbfs
from app.etl.carga_lote import importar_lote_mixto, importar_lote_mixto_stream
from app.etl.dbf_reader import leer_dbf
from app.etl.deteccion import detectar_establecimiento
from app.etl.cenares import contar_filas as contar_filas_cenares
from app.etl.deteccion_tipo import (
    TIPO_CENARES,
    TIPO_ICI,
    TIPO_MOVIM_CAB,
    TIPO_MOVIM_DET,
    TIPO_STOCK_ALMACEN,
    detectar_tipo_archivo,
)
from app.etl.movimientos import contar_lineas_movim, describir_establecimiento_movim
from app.etl.stock_almacen import describir_origen_stock
from app.models.establecimiento import Establecimiento
from app.models.importacion import Incidencia
from app.repositories.importacion_repository import listar_pendientes

router = APIRouter(prefix="/api/importaciones", tags=["importaciones"])


class CandidatoOut(BaseModel):
    cod_2000: str
    nombre: str
    score: float


class PreviewArchivoOut(BaseModel):
    archivo: str
    tipo: str  # ICI | STOCK_ALMACEN | CATALOGO | DESCONOCIDO
    filas: int
    confianza: str | None  # solo ICI: alta | dudosa | no_encontrado
    establecimiento: CandidatoOut | None  # solo ICI
    candidatos: list[CandidatoOut]  # solo ICI
    # Solo STOCK_ALMACEN: si es del almacén o de un establecimiento (por el ALMCOD)
    stock_origen: str | None = None  # ALMACEN | EESS | MIXTO
    stock_establecimiento_cod: str | None = None
    stock_establecimiento_nombre: str | None = None
    error: str | None = None


class PreviewOut(BaseModel):
    archivos: list[PreviewArchivoOut]


class IncidenciaOut(BaseModel):
    id: int
    tipo: str
    detalle: str | None
    fila_id: int | None


class ResumenArchivoMixto(BaseModel):
    archivo: str
    tipo: str
    importacion_id: int | None
    establecimiento: str | None
    filas: int
    incidencias: int
    estado: str  # OK | ERROR | OMITIDO
    error: str | None
    detalle: str | None


class ModuloActualizado(BaseModel):
    pagina: str  # disponibilidad | consolidado | stock | vencimientos
    titulo: str
    detalle: str


class ResumenLote(BaseModel):
    archivos: list[ResumenArchivoMixto]
    productos_recalculados: int
    productos_red_recalculados: int
    modulos: list[ModuloActualizado] = []


class EstablecimientoPendienteOut(BaseModel):
    cod_2000: str
    nombre: str


class PendientesOut(BaseModel):
    periodo: str
    total_establecimientos: int
    cargados: int
    faltantes: list[EstablecimientoPendienteOut]


def _parsear_periodo(periodo: str) -> date:
    try:
        anio_str, mes_str = periodo.split("-")
        return date(int(anio_str), int(mes_str), 1)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400, detail=f"periodo inválido: {periodo!r}, formato esperado AAAA-MM"
        )


@router.post("", response_model=ResumenLote)
async def importar_lote(
    archivos: list[UploadFile] = File(...),
    asignaciones: str = Form(
        "{}",
        description=(
            'JSON {"nombre_archivo.dbf": "cod_2000"} con el establecimiento resuelto '
            "por cada archivo ICI (ver /previsualizar). Solo aplica a los ICI."
        ),
    ),
    periodo: str = Form(..., description="Mes de cierre (aplica a ICI y a la foto de stock), AAAA-MM"),
    usuario: str | None = Form(None),
    db: Session = Depends(get_db),
) -> ResumenLote:
    periodo_fecha = _parsear_periodo(periodo)

    try:
        mapa_asignaciones = json.loads(asignaciones)
        if not isinstance(mapa_asignaciones, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="'asignaciones' debe ser un objeto JSON nombre→cod_2000.")

    # Acepta DBF sueltos o un ZIP (posiblemente mezclado); se expande y cada DBF
    # se enruta a su importador según el tipo detectado por columnas.
    with tempfile.TemporaryDirectory(prefix="carga_") as directorio_tmp:
        try:
            dbfs = await materializar_dbfs(archivos, directorio_tmp)
        except ArchivoNoSoportado as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        lote = importar_lote_mixto(db, dbfs, mapa_asignaciones, periodo_fecha, usuario=usuario)

    return ResumenLote(
        archivos=[
            ResumenArchivoMixto(
                archivo=a.archivo,
                tipo=a.tipo,
                importacion_id=a.importacion_id,
                establecimiento=a.establecimiento,
                filas=a.filas,
                incidencias=a.incidencias,
                estado=a.estado,
                error=a.error,
                detalle=a.detalle,
            )
            for a in lote.archivos
        ],
        productos_recalculados=lote.productos_recalculados,
        productos_red_recalculados=lote.productos_red_recalculados,
        modulos=[ModuloActualizado(**m) for m in lote.modulos],
    )


@router.post("/stream")
async def importar_lote_en_vivo(
    archivos: list[UploadFile] = File(...),
    asignaciones: str = Form("{}"),
    periodo: str = Form(..., description="Mes de cierre (aplica a ICI y a la foto de stock), AAAA-MM"),
    usuario: str | None = Form(None),
):
    """Igual que POST '' pero devolviendo el progreso EN VIVO como NDJSON: un
    evento JSON por línea (plan → archivo_inicio → archivo_fin → recalculo_inicio
    → fin) para que la pantalla muestre archivo por archivo qué va pasando. El
    CPMA se recalcula una sola vez al final (evento 'recalculo_inicio')."""
    periodo_fecha = _parsear_periodo(periodo)
    try:
        mapa_asignaciones = json.loads(asignaciones)
        if not isinstance(mapa_asignaciones, dict):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="'asignaciones' debe ser un objeto JSON nombre→cod_2000.")

    # No se usa TemporaryDirectory (context manager) porque el trabajo ocurre
    # mientras se transmite la respuesta: el directorio se limpia en el finally
    # del generador, cuando el stream termina.
    directorio_tmp = Path(tempfile.mkdtemp(prefix="carga_"))
    try:
        dbfs = await materializar_dbfs(archivos, directorio_tmp)
    except ArchivoNoSoportado as exc:
        shutil.rmtree(directorio_tmp, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc))

    def generar():
        # Sesión propia (el stream corre en un hilo aparte del request).
        db = SessionLocal()
        try:
            for evento in importar_lote_mixto_stream(db, dbfs, mapa_asignaciones, periodo_fecha, usuario=usuario):
                yield json.dumps(evento, default=str) + "\n"
        except Exception as exc:  # falla inesperada: se avisa por el mismo canal
            db.rollback()
            yield json.dumps({"evento": "error", "error": str(exc)}) + "\n"
        finally:
            db.close()
            shutil.rmtree(directorio_tmp, ignore_errors=True)

    return StreamingResponse(
        generar(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/previsualizar", response_model=PreviewOut)
async def previsualizar(
    archivos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> PreviewOut:
    """Analiza los DBF SIN escribir en la BD: acepta DBF sueltos o un ZIP
    (posiblemente mezclado). Por cada DBF detecta el TIPO por columnas y cuenta
    filas; si es ICI, además detecta el establecimiento por el nombre. Alimenta
    el paso 1 (previsualización) para confirmar antes de importar."""
    establecimientos = db.scalars(
        select(Establecimiento)
        .where(Establecimiento.activo, Establecimiento.es_almacen.is_(False))
        .order_by(Establecimiento.nombre)
    ).all()
    catalogo = [(e.cod_2000, e.nombre) for e in establecimientos]

    resultados: list[PreviewArchivoOut] = []
    with tempfile.TemporaryDirectory(prefix="carga_prev_") as directorio_tmp:
        try:
            dbfs = await materializar_dbfs(archivos, directorio_tmp)
        except ArchivoNoSoportado as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        for nombre, ruta in dbfs:
            filas = 0
            error: str | None = None
            tipo = "DESCONOCIDO"
            stock_desc: dict | None = None
            try:
                tipo = detectar_tipo_archivo(ruta)
                if tipo == TIPO_CENARES:
                    filas = contar_filas_cenares(ruta)
                elif tipo in (TIPO_MOVIM_CAB, TIPO_MOVIM_DET):
                    # Movimientos: contar SIN cargar las columnas de paciente.
                    filas = contar_lineas_movim(ruta)
                    if tipo == TIPO_MOVIM_CAB:
                        stock_desc = {"origen": "MOVIM", **describir_establecimiento_movim(ruta, establecimientos), "almacen_cod": None}
                else:
                    filas_datos = leer_dbf(ruta)
                    filas = len(filas_datos)
                    # Stock por lote: distinguir almacén vs establecimiento por el ALMCOD.
                    if tipo == TIPO_STOCK_ALMACEN:
                        stock_desc = describir_origen_stock(filas_datos, establecimientos)
            except Exception as exc:  # archivo ilegible: se reporta, no rompe el lote
                error = str(exc)

            # La detección de establecimiento solo aplica a los ICI.
            if tipo == TIPO_ICI and error is None:
                deteccion = detectar_establecimiento(nombre, catalogo)
                resultados.append(
                    PreviewArchivoOut(
                        archivo=nombre,
                        tipo=tipo,
                        filas=filas,
                        confianza=deteccion.confianza,
                        establecimiento=(
                            CandidatoOut(**vars(deteccion.establecimiento))
                            if deteccion.establecimiento
                            else None
                        ),
                        candidatos=[CandidatoOut(**vars(c)) for c in deteccion.candidatos],
                        error=error,
                    )
                )
            else:
                resultados.append(
                    PreviewArchivoOut(
                        archivo=nombre,
                        tipo=tipo,
                        filas=filas,
                        confianza=None,
                        establecimiento=None,
                        candidatos=[],
                        stock_origen=stock_desc["origen"] if stock_desc else None,
                        stock_establecimiento_cod=stock_desc["establecimiento_cod"] if stock_desc else None,
                        stock_establecimiento_nombre=stock_desc["establecimiento_nombre"] if stock_desc else None,
                        error=error,
                    )
                )

    return PreviewOut(archivos=resultados)


@router.get("/{importacion_id}/incidencias", response_model=list[IncidenciaOut])
def incidencias_de_importacion(
    importacion_id: int,
    db: Session = Depends(get_db),
) -> list[IncidenciaOut]:
    filas = db.scalars(
        select(Incidencia)
        .where(Incidencia.importacion_id == importacion_id)
        .order_by(Incidencia.id)
    ).all()
    return [
        IncidenciaOut(id=i.id, tipo=i.tipo, detalle=i.detalle, fila_id=i.fila_id)
        for i in filas
    ]


@router.get("/pendientes", response_model=PendientesOut)
def obtener_pendientes(
    periodo: str = Query(..., description="AAAA-MM"),
    db: Session = Depends(get_db),
) -> PendientesOut:
    resultado = listar_pendientes(db, _parsear_periodo(periodo))
    return PendientesOut(
        periodo=resultado["periodo"].strftime("%Y-%m"),
        total_establecimientos=resultado["total_establecimientos"],
        cargados=resultado["cargados"],
        faltantes=[EstablecimientoPendienteOut(**f) for f in resultado["faltantes"]],
    )
