import { useState } from "react";
import type { Situacion } from "../services/types";
import { SITUACION_META } from "../services/situacion";

export interface ItemSituacion {
  situacion: Situacion;
  cantidad: number;
  porcentaje: number;
}

interface Props {
  /** Total de productos visibles (= el contador de la tabla). */
  total: number;
  /** Desglose por situación, en orden de urgencia, solo los presentes. */
  items: ItemSituacion[];
  situacionActiva: Situacion | "";
  onSituacionSelect: (s: Situacion) => void;
}

/** Resumen dinámico de situación de lo que el doc está viendo (reacciona a los
 * filtros: el `total` y los `items` se calculan sobre las filas ya filtradas).
 * Mismo lenguaje visual que el resumen Soporte/SIS de la red. Compacto y
 * colapsable para no empujar la tabla. */
export function ResumenSituacionFiltrado({ total, items, situacionActiva, onSituacionSelect }: Props) {
  const [abierto, setAbierto] = useState(true);

  if (total === 0) return null;

  return (
    <div className="card mb-3">
      <div className="card-body py-2">
        <div className="d-flex align-items-center gap-3 flex-wrap">
          <button
            type="button"
            className="btn btn-sm btn-link p-0 text-body text-decoration-none d-inline-flex align-items-center gap-1"
            onClick={() => setAbierto((v) => !v)}
            aria-expanded={abierto}
            title={abierto ? "Plegar" : "Expandir"}
          >
            <i className={`bi ${abierto ? "bi-chevron-down" : "bi-chevron-right"}`} aria-hidden="true" />
            <span className="fw-semibold">Situación de lo que ves</span>
            <span className="text-body-secondary">· {total.toLocaleString("es-PE")} productos</span>
          </button>

          {/* Barra proporcional, siempre visible (panorama de un vistazo). */}
          <div
            className="d-flex rounded overflow-hidden flex-grow-1"
            style={{ height: 14, minWidth: 160, maxWidth: 520 }}
            role="img"
            aria-label="Distribución por situación"
          >
            {items.map((item) => {
              const meta = SITUACION_META[item.situacion];
              const atenuada = situacionActiva !== "" && situacionActiva !== item.situacion;
              return (
                <div
                  key={item.situacion}
                  title={`${meta.label}: ${item.porcentaje}% (${item.cantidad})`}
                  onClick={() => onSituacionSelect(item.situacion)}
                  style={{ width: `${item.porcentaje}%`, backgroundColor: meta.color, cursor: "pointer", opacity: atenuada ? 0.3 : 1 }}
                />
              );
            })}
          </div>

          {situacionActiva && (
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => onSituacionSelect(situacionActiva)}>
              <i className="bi bi-x-lg me-1" aria-hidden="true" />
              Quitar filtro
            </button>
          )}
        </div>

        {abierto && (
          <div className="d-flex flex-wrap gap-1 mt-2">
            {items.map((item) => {
              const meta = SITUACION_META[item.situacion];
              const activa = situacionActiva === item.situacion;
              const atenuada = situacionActiva !== "" && !activa;
              return (
                <button
                  key={item.situacion}
                  type="button"
                  onClick={() => onSituacionSelect(item.situacion)}
                  title={meta.descripcion}
                  aria-pressed={activa}
                  className="btn btn-sm d-inline-flex align-items-center gap-1"
                  style={{
                    borderWidth: 2,
                    borderStyle: "solid",
                    borderColor: meta.color,
                    backgroundColor: activa ? meta.color : "transparent",
                    color: activa ? (meta.textoOscuro ? "#000" : "#fff") : undefined,
                    opacity: atenuada ? 0.5 : 1,
                    fontSize: "0.78rem",
                  }}
                >
                  <i className={`bi ${meta.icono}`} style={{ color: activa ? "inherit" : meta.color }} aria-hidden="true" />
                  <span className="fw-semibold">{meta.label}</span>
                  <strong>{item.porcentaje}%</strong>
                  <span className={activa ? "" : "text-body-secondary"}>({item.cantidad})</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
