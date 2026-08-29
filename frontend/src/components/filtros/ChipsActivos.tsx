export interface ChipActivo {
  clave: string;
  etiqueta: string; // ej. "Tipo: Medicamento"
  onQuitar: () => void;
}

interface Props {
  chips: ChipActivo[];
  onLimpiar: () => void;
  /** Texto del contador de resultados, ej. "42 productos". */
  contador?: string;
  cargando?: boolean;
}

/** Chips de los filtros activos (cada uno con "x"), botón "Limpiar todo" y el
 * contador de resultados — siempre visible qué está filtrado. */
export function ChipsActivos({ chips, onLimpiar, contador, cargando }: Props) {
  const hay = chips.length > 0;
  return (
    <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
      {cargando ? (
        <span className="text-body-secondary small">
          <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
          Consultando…
        </span>
      ) : (
        contador && (
          <span className="badge text-bg-light border fs-6 fw-semibold">
            <i className="bi bi-funnel me-1" aria-hidden="true" />
            {contador}
          </span>
        )
      )}

      {hay && <span className="text-body-secondary small ms-1">Filtros:</span>}

      {chips.map((c) => (
        <span key={c.clave} className="badge rounded-pill text-bg-primary d-inline-flex align-items-center gap-1">
          {c.etiqueta}
          <button
            type="button"
            className="btn-close btn-close-white"
            style={{ fontSize: "0.6rem" }}
            aria-label={`Quitar ${c.etiqueta}`}
            onClick={c.onQuitar}
          />
        </span>
      ))}

      {hay && (
        <button type="button" className="btn btn-sm btn-link text-decoration-none p-0 ms-1" onClick={onLimpiar}>
          Limpiar todo
        </button>
      )}
    </div>
  );
}
