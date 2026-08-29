import { Fragment, useState } from "react";
import { obtenerIncidencias } from "../../services/api";
import type { IncidenciaOut, ResumenLoteImportacion } from "../../services/types";
import { BadgeTipo } from "./BadgeTipo";

interface Props {
  resumen: ResumenLoteImportacion;
  nombrePorCod: Map<string, string>;
  onNuevaCarga: () => void;
  /** Salta al módulo actualizado (Disponibilidad, Stock, Vencimientos, Consolidado). */
  onIrAModulo?: (pagina: string) => void;
}

const ICONO_MODULO: Record<string, string> = {
  disponibilidad: "bi-clipboard-data",
  consolidado: "bi-diagram-3",
  stock: "bi-box-seam",
  vencimientos: "bi-calendar-x",
};

interface EstadoDetalle {
  cargando: boolean;
  error: string | null;
  items: IncidenciaOut[] | null;
}

function numero(valor: number): string {
  return valor.toLocaleString("es-PE");
}

function Tarjeta({ titulo, valor, icono, color }: { titulo: string; valor: string; icono: string; color: string }) {
  return (
    <div className="col-sm-6 col-lg-3">
      <div className="card h-100">
        <div className="card-body d-flex align-items-center gap-3">
          <i className={`bi ${icono} fs-2 ${color}`} aria-hidden="true" />
          <div>
            <div className="fs-4 fw-semibold">{valor}</div>
            <div className="text-body-secondary small">{titulo}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ResumenLote({ resumen, nombrePorCod, onNuevaCarga, onIrAModulo }: Props) {
  const [detalles, setDetalles] = useState<Record<number, EstadoDetalle>>({});
  const [abierto, setAbierto] = useState<Record<number, boolean>>({});

  function alternarDetalle(importacionId: number) {
    const yaAbierto = abierto[importacionId];
    setAbierto((prev) => ({ ...prev, [importacionId]: !yaAbierto }));
    if (yaAbierto || detalles[importacionId]) return;

    setDetalles((prev) => ({ ...prev, [importacionId]: { cargando: true, error: null, items: null } }));
    obtenerIncidencias(importacionId)
      .then((items) =>
        setDetalles((prev) => ({ ...prev, [importacionId]: { cargando: false, error: null, items } })),
      )
      .catch((error: unknown) =>
        setDetalles((prev) => ({
          ...prev,
          [importacionId]: {
            cargando: false,
            error: error instanceof Error ? error.message : "Error desconocido",
            items: null,
          },
        })),
      );
  }

  const conError = resumen.archivos.filter((a) => a.estado !== "OK").length;
  const ok = resumen.archivos.length - conError;
  const totalFilas = resumen.archivos.reduce((s, a) => s + a.filas, 0);
  const totalIncidencias = resumen.archivos.reduce((s, a) => s + a.incidencias, 0);

  return (
    <>
      {resumen.modulos.length > 0 && (
        <div className="card border-success-subtle mb-3">
          <div className="card-body">
            <h6 className="text-success fw-semibold mb-3">
              <i className="bi bi-check2-all me-2" aria-hidden="true" />
              Listo. Se actualizaron estos módulos:
            </h6>
            <div className="d-flex flex-wrap gap-2">
              {resumen.modulos.map((m) => (
                <button
                  key={m.pagina + m.titulo}
                  type="button"
                  className="btn btn-outline-success text-start d-flex align-items-center gap-2"
                  style={{ minWidth: 240 }}
                  onClick={() => onIrAModulo?.(m.pagina)}
                >
                  <i className={`bi ${ICONO_MODULO[m.pagina] ?? "bi-box-arrow-in-right"} fs-4`} aria-hidden="true" />
                  <span className="flex-grow-1">
                    <span className="fw-semibold d-block">{m.titulo}</span>
                    <span className="small text-body-secondary">{m.detalle}</span>
                  </span>
                  <i className="bi bi-arrow-right" aria-hidden="true" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="row g-3 mb-3">
        <Tarjeta titulo="Archivos importados" valor={`${ok}/${resumen.archivos.length}`} icono="bi-check2-circle" color="text-success" />
        <Tarjeta titulo="Filas procesadas" valor={numero(totalFilas)} icono="bi-database-add" color="text-primary" />
        <Tarjeta titulo="Incidencias" valor={numero(totalIncidencias)} icono="bi-exclamation-triangle" color={totalIncidencias ? "text-warning" : "text-body-secondary"} />
        <Tarjeta titulo="CPMA recalculado" valor={numero(resumen.productos_recalculados)} icono="bi-calculator" color="text-primary" />
      </div>

      <div className="card mb-3">
        <div className="card-body p-0">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Archivo</th>
                <th>Tipo</th>
                <th>Destino</th>
                <th className="text-center">Estado</th>
                <th className="text-end">Filas</th>
                <th className="text-end">Incidencias</th>
              </tr>
            </thead>
            <tbody>
              {resumen.archivos.map((a) => {
                const destino =
                  a.tipo === "ICI"
                    ? a.establecimiento
                      ? nombrePorCod.get(a.establecimiento) ?? a.establecimiento
                      : "—"
                    : a.detalle ?? "—";
                const puedeVerDetalle = a.incidencias > 0 && a.importacion_id != null;
                const estaAbierto = a.importacion_id != null && abierto[a.importacion_id];
                const detalle = a.importacion_id != null ? detalles[a.importacion_id] : undefined;

                return (
                  <Fragment key={a.archivo}>
                    <tr className={a.estado === "ERROR" ? "table-danger" : a.estado === "OMITIDO" ? "table-warning" : undefined}>
                      <td>{a.archivo}</td>
                      <td>
                        <BadgeTipo tipo={a.tipo} />
                      </td>
                      <td className="text-body-secondary small">{destino}</td>
                      <td className="text-center">
                        {a.estado === "OK" ? (
                          <span className="badge text-bg-success">OK</span>
                        ) : a.estado === "OMITIDO" ? (
                          <span className="badge text-bg-warning" title={a.error ?? undefined}>OMITIDO</span>
                        ) : (
                          <span className="badge text-bg-danger" title={a.error ?? undefined}>ERROR</span>
                        )}
                      </td>
                      <td className="text-end">{numero(a.filas)}</td>
                      <td className="text-end">
                        {a.incidencias > 0 ? (
                          <span className="text-warning fw-semibold">{numero(a.incidencias)}</span>
                        ) : (
                          <span className="text-body-secondary">0</span>
                        )}
                        {puedeVerDetalle && (
                          <button
                            type="button"
                            className="btn btn-sm btn-link p-0 ms-2 align-baseline"
                            onClick={() => alternarDetalle(a.importacion_id!)}
                          >
                            {estaAbierto ? "ocultar" : "ver detalle"}
                          </button>
                        )}
                      </td>
                    </tr>

                    {estaAbierto && (
                      <tr>
                        <td colSpan={6} className="bg-body-tertiary">
                          {detalle?.cargando && (
                            <span className="text-body-secondary small">
                              <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                              Cargando incidencias…
                            </span>
                          )}
                          {detalle?.error && (
                            <span className="text-danger small">No se pudieron cargar: {detalle.error}</span>
                          )}
                          {detalle?.items && (
                            <table className="table table-sm mb-0">
                              <thead>
                                <tr className="text-body-secondary small">
                                  <th style={{ width: "16rem" }}>Tipo</th>
                                  <th>Detalle</th>
                                </tr>
                              </thead>
                              <tbody>
                                {detalle.items.slice(0, 200).map((inc) => (
                                  <tr key={inc.id}>
                                    <td>
                                      <code className="small">{inc.tipo}</code>
                                    </td>
                                    <td className="small">{inc.detalle}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                          {detalle?.items && detalle.items.length > 200 && (
                            <div className="text-body-secondary small p-2">
                              Mostrando 200 de {detalle.items.length} incidencias.
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <button type="button" className="btn btn-primary" onClick={onNuevaCarga}>
        <i className="bi bi-arrow-repeat me-1" aria-hidden="true" />
        Cargar otro lote
      </button>
    </>
  );
}
