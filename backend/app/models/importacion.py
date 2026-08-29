"""Identidad de cada importación y sus incidencias."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Importacion(Base):
    __tablename__ = "importacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    archivo: Mapped[str] = mapped_column(String(255))
    establecimiento_cod: Mapped[str | None] = mapped_column(String(20))
    periodo: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1)
    filas_cabecera: Mapped[int] = mapped_column(Integer, default=0)
    filas_detalle: Mapped[int] = mapped_column(Integer, default=0)
    incidencias: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(20), default="PENDIENTE")
    usuario: Mapped[str | None] = mapped_column(String(100))
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Incidencia(Base):
    __tablename__ = "incidencia"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    importacion_id: Mapped[int] = mapped_column(ForeignKey("importacion.id", ondelete="CASCADE"))
    tabla_origen: Mapped[str | None] = mapped_column(String(30))
    fila_id: Mapped[int | None] = mapped_column(BigInteger)
    tipo: Mapped[str] = mapped_column(String(50))
    detalle: Mapped[str | None] = mapped_column(Text)
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
