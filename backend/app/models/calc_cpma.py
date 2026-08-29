"""CPMA precalculado por establecimiento/producto. Ver app/services/cpma.py
(motor) y app/repositories/cpma_repository.py (quién lo llena)."""
from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CalcCpma(Base):
    __tablename__ = "calc_cpma"

    establecimiento_id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    periodo: Mapped[date_] = mapped_column(Date, primary_key=True)

    sumames: Mapped[float] = mapped_column(Numeric(16, 2))
    contador: Mapped[int] = mapped_column(SmallInteger)
    cpma: Mapped[float] = mapped_column(Numeric(14, 2))
    stock_red: Mapped[float] = mapped_column(Numeric(14, 2), default=0)  # Red (establecimiento)
    stock_aem: Mapped[float] = mapped_column(Numeric(14, 2), default=0)  # Almacén (AEM central)
    dispo: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # stock_red / cpma
    dispo_total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # (stock_red+stock_aem)/cpma
    situacion: Mapped[str] = mapped_column(String(20))
    situacion_total: Mapped[str] = mapped_column(String(20))
    calculado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
