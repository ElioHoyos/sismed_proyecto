"""% DME precalculado por establecimiento y consolidado de red.
Ver app/services/dme.py (motor) y app/repositories/dme_repository.py (quién lo llena)."""
from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CalcDme(Base):
    __tablename__ = "calc_dme"

    establecimiento_id: Mapped[int] = mapped_column(ForeignKey("establecimiento.id"), primary_key=True)
    periodo: Mapped[date_] = mapped_column(Date, primary_key=True)

    total_evaluados: Mapped[int] = mapped_column(SmallInteger)
    total_disponibles: Mapped[int] = mapped_column(SmallInteger)
    porcentaje: Mapped[float] = mapped_column(Numeric(5, 2))
    semaforo: Mapped[str] = mapped_column(String(20))
    calculado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CalcDmeRed(Base):
    __tablename__ = "calc_dme_red"

    periodo: Mapped[date_] = mapped_column(Date, primary_key=True)

    total_evaluados: Mapped[int] = mapped_column(SmallInteger)
    total_disponibles: Mapped[int] = mapped_column(SmallInteger)
    porcentaje: Mapped[float] = mapped_column(Numeric(5, 2))
    semaforo: Mapped[str] = mapped_column(String(20))
    calculado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
