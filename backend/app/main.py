from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.asistente import router as asistente_router
from app.api.compra import router as compra_router
from app.api.consolidado import router as consolidado_router
from app.api.disponibilidad import router as disponibilidad_router
from app.api.exportar_api import router as exportar_router
from app.api.dme import router as dme_router
from app.api.establecimientos import router as establecimientos_router
from app.api.importaciones import router as importaciones_router
from app.api.movimientos import router as movimientos_router
from app.api.stock import router as stock_router

tags_metadata = [
    {
        "name": "importaciones",
        "description": "Carga del ICI (DBF por establecimiento) y estado de qué falta por cargar en un periodo.",
    },
    {
        "name": "disponibilidad",
        "description": "Disponibilidad, situación y requisición sugerida — leídas de calc_cpma/calc_cpma_red.",
    },
    {
        "name": "dme",
        "description": "% DME (Disponibilidad de Medicamentos Esenciales) por establecimiento y de red.",
    },
]

app = FastAPI(
    title="Sistema de Gestión de Medicamentos — Red Coronel Portillo",
    description=(
        "API de disponibilidad y CPMA para la Red de Salud Coronel Portillo. "
        "Reemplaza el cálculo manual del CPMA en Excel."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # para leer el nombre del archivo al exportar
)

app.include_router(importaciones_router)
app.include_router(disponibilidad_router)
app.include_router(dme_router)
app.include_router(establecimientos_router)
app.include_router(stock_router)
app.include_router(asistente_router)
app.include_router(exportar_router)
app.include_router(compra_router)
app.include_router(consolidado_router)
app.include_router(movimientos_router)


@app.on_event("startup")
def sembrar_historial_al_arrancar() -> None:
    """Backfill de negativos preexistentes: al arrancar, siembra en el historial
    los negativos que ya estaban en el stock antes del motor (idempotente)."""
    from app.core.db import SessionLocal
    from app.repositories.historial_stock_repository import sembrar_historial_desde_stock

    db = SessionLocal()
    try:
        creadas = sembrar_historial_desde_stock(db)
        if creadas:
            print(f"[historial] backfill: {creadas} incidencia(s) de negativos preexistentes sembradas.")
    finally:
        db.close()
