"""Movimientos de kardex (entradas/salidas) de un establecimiento, de TMOVIM +
TMOVIMDET (FoxPro del puesto).

PRIVACIDAD — CRÍTICO: los archivos de origen traen datos personales de pacientes
(nombres en MOVREFE, DNI_CLIE, diagnósticos DIAGCOD*, PCTCOD, PERCOD, CLICOD).
NADA de eso se importa ni se guarda aquí. Este es un sistema de gestión de
medicamentos, no de historia clínica. De MOVREFE solo se deriva una CATEGORÍA
genérica (SIS / GENERAL / INTERV. SANITARIA / NOMINAL) — el texto original nunca
se persiste. Ver app/etl/movimientos.py.

Volumen: un puesto trae ~78.000 líneas; índices por producto/fecha/establecimiento
para que la consulta de kardex y consumo escale."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Categoría de salida derivada de MOVREFE (sin guardar el texto/paciente).
CAT_SIS = "SIS"
CAT_GENERAL = "GENERAL"
CAT_INTERV = "INTERV. SANITARIA"
CAT_NOMINAL = "NOMINAL"  # dispensación a paciente: se agrupa, nunca el nombre


class Movimiento(Base):
    __tablename__ = "movimiento"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    establecimiento_id: Mapped[int] = mapped_column(ForeignKey("establecimiento.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"))
    tipo: Mapped[str] = mapped_column(String(1))  # E (entrada) | S (salida)
    numero: Mapped[str | None] = mapped_column(String(12))  # MOVNUMERO
    item: Mapped[str | None] = mapped_column(String(6))  # MOVNUMEITE (línea)
    fecha_emision: Mapped[datetime | None] = mapped_column(DateTime)  # MOVFECHEMI
    fecha_registro: Mapped[datetime | None] = mapped_column(DateTime)  # MOVFECHREG
    lote: Mapped[str | None] = mapped_column(String(40))  # MEDLOTE
    fecha_vcto: Mapped[date | None] = mapped_column(Date)  # MEDFECHVTO
    cantidad: Mapped[float] = mapped_column(Numeric(14, 2))  # MOVCANTID
    precio: Mapped[float | None] = mapped_column(Numeric(14, 6))  # MOVPRECIO
    total: Mapped[float | None] = mapped_column(Numeric(16, 6))  # MOVTOTAL
    tipsum: Mapped[str | None] = mapped_column(String(4))  # TIPSUM
    ffinan: Mapped[str | None] = mapped_column(String(4))  # FFINAN
    categoria: Mapped[str | None] = mapped_column(String(20))  # solo salidas
    importacion_id: Mapped[int | None] = mapped_column(ForeignKey("importacion.id"))
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_mov_prod", "establecimiento_id", "producto_id", "fecha_emision"),
        Index("ix_mov_fecha", "establecimiento_id", "fecha_emision"),
        Index("ix_mov_consumo", "establecimiento_id", "producto_id", "tipo", "fecha_emision"),
    )
