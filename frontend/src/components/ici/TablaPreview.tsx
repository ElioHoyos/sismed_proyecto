import type { EstablecimientoOut, PreviewArchivo } from "../../services/types";
import type { EntradaArchivo } from "../../pages/CargaPage";
import { BadgeConfianza } from "./BadgeConfianza";
import { BadgeTipo } from "./BadgeTipo";

interface Props {
  entradas: EntradaArchivo[];
  establecimientos: EstablecimientoOut[];
  onCambiarEstablecimiento: (archivo: string, cod2000: string) => void;
  onQuitar: (archivo: string) => void;
}

function numero(valor: number): string {
  return valor.toLocaleString("es-PE");
}

/** Para un archivo de stock por lote: si es del almacén o de un establecimiento
 * (resuelto por el ALMCOD en el backend). */
function DestinoStock({ p }: { p: PreviewArchivo }) {
  if (p.stock_origen === "EESS") {
    return (
      <span className="small">
        <span className="badge text-bg-success-subtle border me-1">
          <i className="bi bi-hospital me-1" aria-hidden="true" />
          Establecimiento
        </span>
        {p.stock_establecimiento_nombre ?? "—"}
        {p.stock_establecimiento_cod ? ` (${p.stock_establecimiento_cod})` : ""} — stock por lote
      </span>
    );
  }
  if (p.stock_origen === "ALMACEN") {
    return (
      <span className="small">
        <span className="badge text-bg-primary-subtle border me-1">
          <i className="bi bi-building me-1" aria-hidden="true" />
          Almacén central
        </span>
        stock por lote
      </span>
    );
  }
  return (
    <span className="text-body-secondary small">
      <i className="bi bi-box-seam me-1" aria-hidden="true" />
      Stock por lote
    </span>
  );
}

function BotonQuitar({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="btn btn-sm btn-outline-secondary"
      onClick={onClick}
      title="Quitar del lote"
    >
      <i className="bi bi-x-lg" aria-hidden="true" />
    </button>
  );
}

export function TablaPreview({
  entradas,
  establecimientos,
  onCambiarEstablecimiento,
  onQuitar,
}: Props) {
  return (
    <div className="card mb-3">
      <div className="card-body p-0">
        <div style={{ maxHeight: "60vh", overflow: "auto" }}>
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light sticky-top">
              <tr>
                <th>Archivo</th>
                <th>Tipo</th>
                <th className="text-end">Filas</th>
                <th style={{ minWidth: "22rem" }}>Establecimiento / Destino</th>
                <th className="text-center" style={{ width: "3rem" }} aria-label="Quitar" />
              </tr>
            </thead>
            <tbody>
              {entradas.map((entrada) => {
                const p = entrada.preview;

                if (p.error) {
                  return (
                    <tr key={entrada.archivo} className="table-danger">
                      <td>
                        <i className="bi bi-file-earmark-x me-2" aria-hidden="true" />
                        {entrada.archivo}
                      </td>
                      <td>
                        <BadgeTipo tipo={p.tipo} />
                      </td>
                      <td colSpan={2} className="text-danger small">
                        No se pudo leer: {p.error}
                      </td>
                      <td className="text-center">
                        <BotonQuitar onClick={() => onQuitar(entrada.archivo)} />
                      </td>
                    </tr>
                  );
                }

                const esIci = p.tipo === "ICI";
                const desconocido = p.tipo === "DESCONOCIDO";
                const sinAsignar = esIci && entrada.codigoAsignado === "";

                return (
                  <tr
                    key={entrada.archivo}
                    className={sinAsignar ? "table-warning" : desconocido ? "table-danger" : undefined}
                  >
                    <td>
                      <i className="bi bi-file-earmark-binary me-2 text-primary" aria-hidden="true" />
                      {entrada.archivo}
                    </td>
                    <td>
                      <BadgeTipo tipo={p.tipo} />
                    </td>
                    <td className="text-end">{numero(p.filas)}</td>
                    <td>
                      {esIci ? (
                        <div className="d-flex align-items-center gap-2">
                          {p.confianza && <BadgeConfianza confianza={p.confianza} />}
                          <select
                            className={`form-select form-select-sm ${sinAsignar ? "border-warning" : ""}`}
                            value={entrada.codigoAsignado}
                            onChange={(e) => onCambiarEstablecimiento(entrada.archivo, e.target.value)}
                            aria-label={`Establecimiento para ${entrada.archivo}`}
                          >
                            <option value="">— Selecciona establecimiento —</option>
                            {establecimientos.map((est) => (
                              <option key={est.cod_2000} value={est.cod_2000}>
                                {est.nombre}
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : desconocido ? (
                        <span className="text-danger small">
                          Tipo no reconocido — no se importará
                        </span>
                      ) : p.tipo === "STOCK_ALMACEN" ? (
                        <DestinoStock p={p} />
                      ) : (
                        <span className="text-body-secondary small">
                          <i className="bi bi-check2 me-1" aria-hidden="true" />
                          No requiere establecimiento
                        </span>
                      )}
                    </td>
                    <td className="text-center">
                      <BotonQuitar onClick={() => onQuitar(entrada.archivo)} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
