"""Historial de vida de cada incidencia de stock (por ahora, negativos por lote),
identificada por establecimiento/almacén + producto + lote.

Vive APARTE del stock (que se reemplaza en cada carga): estas tablas NO se
borran, son el historial. El estado 'resuelto' se detecta SOLO comparando la
foto nueva contra la anterior (el dato manda, no depende del check humano). El
check del informático (`revision_stock`) agrega el 'quién/cuándo lo atendió' y
sobrevive a las recargas. Ver app/repositories/historial_stock_repository.py."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

TIPO_NEGATIVO = "NEGATIVO"  # futuro: VENCIDO / POR_VENCER (2ª fase)
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_RESUELTO = "RESUELTO"


class IncidenciaStock(Base):
    __tablename__ = "incidencia_stock"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), default=TIPO_NEGATIVO)
    # Ubicación: solo uno de los dos según el origen.
    origen: Mapped[str] = mapped_column(String(10))  # ALMACEN | EESS_LOTE
    almacen_cod: Mapped[str | None] = mapped_column(String(20))
    establecimiento_id: Mapped[int | None] = mapped_column(ForeignKey("establecimiento.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"))
    medcod: Mapped[str] = mapped_column(String(20))
    lote: Mapped[str] = mapped_column(String(80))

    # Detectado: primera carga en que apareció, con su valor (ej. −10).
    detectado_en: Mapped[datetime] = mapped_column(DateTime)
    detectado_importacion_id: Mapped[int | None] = mapped_column(ForeignKey("importacion.id"))
    valor_detectado: Mapped[float] = mapped_column(Numeric(14, 2))
    # True si se sembró del stock que YA existía al arrancar el motor (no se vio
    # "aparecer"): la fecha de detección es la del backfill, no el momento real.
    detectado_inicial: Mapped[bool] = mapped_column(Boolean, default=False)
    # Mientras sigue pendiente: último valor visto y última carga que lo confirmó.
    valor_actual: Mapped[float] = mapped_column(Numeric(14, 2))
    ultima_carga_en: Mapped[datetime] = mapped_column(DateTime)

    estado: Mapped[str] = mapped_column(String(12), default=ESTADO_PENDIENTE)
    # Resuelto: carga posterior en que desapareció, con el valor nuevo (0/positivo).
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime)
    resuelto_importacion_id: Mapped[int | None] = mapped_column(ForeignKey("importacion.id"))
    valor_resuelto: Mapped[float | None] = mapped_column(Numeric(14, 2))

    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RevisionStock(Base):
    """El check del informático sobre una incidencia: 'revisado/corregido', con
    quién y una nota opcional. Tabla aparte, sobrevive a las recargas. Es parte de
    la línea de tiempo, no un estado suelto."""
    __tablename__ = "revision_stock"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    incidencia_id: Mapped[int] = mapped_column(
        ForeignKey("incidencia_stock.id", ondelete="CASCADE"), unique=True
    )
    revisado_por: Mapped[str | None] = mapped_column(String(100))
    nota: Mapped[str | None] = mapped_column(Text)
    revisado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
