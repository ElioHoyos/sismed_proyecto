import type { TipoArchivo } from "../../services/types";

const META: Record<TipoArchivo, { label: string; clase: string; icono: string }> = {
  ICI: { label: "ICI (consumo)", clase: "text-bg-primary", icono: "bi-graph-up" },
  STOCK_ALMACEN: { label: "Stock almacén", clase: "text-bg-info", icono: "bi-box-seam" },
  CATALOGO: { label: "Catálogo", clase: "text-bg-secondary", icono: "bi-journal-text" },
  CENARES: { label: "Compra CENARES", clase: "text-bg-warning", icono: "bi-cart-check" },
  MOVIM_CAB: { label: "Movimientos (cabecera)", clase: "text-bg-success", icono: "bi-arrow-left-right" },
  MOVIM_DET: { label: "Movimientos (detalle)", clase: "text-bg-success", icono: "bi-arrow-left-right" },
  DESCONOCIDO: { label: "Desconocido", clase: "text-bg-danger", icono: "bi-question-circle" },
};

export function BadgeTipo({ tipo }: { tipo: TipoArchivo }) {
  const meta = META[tipo];
  return (
    <span className={`badge ${meta.clase} d-inline-flex align-items-center gap-1`}>
      <i className={`bi ${meta.icono}`} aria-hidden="true" />
      {meta.label}
    </span>
  );
}
