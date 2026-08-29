import type { ResumenArchivoImportacion, TipoArchivo } from "../../services/types";
import { BadgeTipo } from "./BadgeTipo";

export type EstadoProgreso = "en_cola" | "procesando" | "OK" | "ERROR" | "OMITIDO";

export interface FilaProgreso {
  archivo: string;
  tipo: TipoArchivo;
  estado: EstadoProgreso;
  resultado?: ResumenArchivoImportacion;
}

interface Props {
  filas: FilaProgreso[];
  /** true mientras corre el recálculo final (CPMA, disponibilidad, DME). */
  recalculando: boolean;
  /** true cuando ya terminó todo (se llegó al evento "fin"). */
  terminado: boolean;
}

function numero(valor: number): string {
  return valor.toLocaleString("es-PE");
}

function IconoEstado({ estado }: { estado: EstadoProgreso }) {
  switch (estado) {
    case "en_cola":
      return <i className="bi bi-hourglass-split text-body-tertiary fs-5" title="En cola" aria-hidden="true" />;
    case "procesando":
      return <span className="spinner-border spinner-border-sm text-primary" role="status" aria-label="Procesando" />;
    case "OK":
      return <i className="bi bi-check-circle-fill text-success fs-5" title="Listo" aria-hidden="true" />;
    case "OMITIDO":
      return <i className="bi bi-slash-circle-fill text-warning fs-5" title="Omitido" aria-hidden="true" />;
    case "ERROR":
      return <i className="bi bi-x-circle-fill text-danger fs-5" title="Error" aria-hidden="true" />;
  }
}

function textoEstado(f: FilaProgreso): string {
  switch (f.estado) {
    case "en_cola":
      return "En cola…";
    case "procesando":
      return "Procesando…";
    case "OMITIDO":
      return f.resultado?.error ?? "Omitido";
    case "ERROR":
      return f.resultado?.error ?? "Error";
    case "OK": {
      const r = f.resultado;
      if (!r) return "Listo";
      const partes = [`${numero(r.filas)} filas`];
      if (r.incidencias > 0) partes.push(`${numero(r.incidencias)} incidencias`);
      if (r.detalle) partes.push(r.detalle);
      return partes.join(" · ");
    }
  }
}

export function ProgresoLote({ filas, recalculando, terminado }: Props) {
  const hechos = filas.filter((f) => f.estado !== "en_cola" && f.estado !== "procesando").length;

  return (
    <div className="card mb-3">
      <div className="card-header d-flex align-items-center gap-2">
        {terminado ? (
          <i className="bi bi-check2-all text-success" aria-hidden="true" />
        ) : (
          <span className="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true" />
        )}
        <span className="fw-semibold">
          {terminado ? "Importación terminada" : "Importando…"}
        </span>
        <span className="text-body-secondary small ms-auto">
          {hechos} de {filas.length} archivo{filas.length === 1 ? "" : "s"}
        </span>
      </div>
      <ul className="list-group list-group-flush">
        {filas.map((f) => {
          const activo = f.estado === "procesando";
          const malo = f.estado === "ERROR";
          const omitido = f.estado === "OMITIDO";
          return (
            <li
              key={f.archivo}
              className="list-group-item d-flex align-items-start gap-3"
              style={{
                background: activo ? "rgba(13,110,253,0.06)" : malo ? "rgba(220,53,69,0.05)" : omitido ? "rgba(255,193,7,0.08)" : undefined,
                transition: "background-color .2s ease",
              }}
            >
              <div style={{ width: 24, textAlign: "center", paddingTop: 2 }}>
                <IconoEstado estado={f.estado} />
              </div>
              <div className="flex-grow-1">
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <span className="fw-semibold">{f.archivo}</span>
                  <BadgeTipo tipo={f.tipo} />
                </div>
                <div
                  className={`small ${malo ? "text-danger" : omitido ? "text-warning-emphasis" : "text-body-secondary"}`}
                >
                  {textoEstado(f)}
                </div>
              </div>
            </li>
          );
        })}

        {/* Paso final: recálculo de indicadores (por qué tarda unos segundos). */}
        {(recalculando || (terminado && filas.some((f) => f.estado === "OK"))) && (
          <li className="list-group-item d-flex align-items-start gap-3">
            <div style={{ width: 24, textAlign: "center", paddingTop: 2 }}>
              {recalculando ? (
                <span className="spinner-border spinner-border-sm text-primary" role="status" aria-label="Recalculando" />
              ) : (
                <i className="bi bi-check-circle-fill text-success fs-5" aria-hidden="true" />
              )}
            </div>
            <div className="flex-grow-1">
              <div className="fw-semibold">Recalculando indicadores…</div>
              <div className="small text-body-secondary">
                CPMA, disponibilidad y % DME (una sola vez, al final del lote).
              </div>
            </div>
          </li>
        )}
      </ul>
    </div>
  );
}
