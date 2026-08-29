import { useEffect, useState } from "react";
import { obtenerFueraCatalogo } from "../services/api";
import type { FueraCatalogoRow, OrigenStock } from "../services/types";

interface Props {
  origen: OrigenStock;
  establecimientoCod: string;
  /** Si el origen actual muestra stock por lote (si no, no aplica el concepto). */
  aplica: boolean;
}

function numero(valor: number): string {
  return valor.toLocaleString("es-PE", { maximumFractionDigits: 2 });
}
function fechaCorta(iso: string | null): string {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}

/** Reporte de productos que un puesto (o el almacén) tiene por lote pero que NO
 * están en el catálogo del almacén. No es un error a corregir: el puesto los
 * maneja por vía externa (DIRESA/CENARES/donación). Dato para que el doc decida
 * si algo debe incorporarse al catálogo central. */
export function PanelFueraCatalogo({ origen, establecimientoCod, aplica }: Props) {
  const [filas, setFilas] = useState<FueraCatalogoRow[]>([]);
  const [cargando, setCargando] = useState(false);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    if (!aplica) {
      setFilas([]);
      return;
    }
    let vigente = true;
    setCargando(true);
    obtenerFueraCatalogo({ origen, establecimientoCod })
      .then((r) => vigente && setFilas(r.resultados))
      .catch(() => vigente && setFilas([]))
      .finally(() => vigente && setCargando(false));
    return () => {
      vigente = false;
    };
  }, [origen, establecimientoCod, aplica]);

  if (!aplica || cargando || filas.length === 0) return null;

  return (
    <div className="card mb-2 border-info-subtle">
      <div className="card-body py-2">
        <button
          type="button"
          className="btn btn-link p-0 text-decoration-none d-flex align-items-center gap-2 w-100 text-start"
          onClick={() => setAbierto((v) => !v)}
          aria-expanded={abierto}
        >
          <i className="bi bi-clipboard-plus text-info fs-5" aria-hidden="true" />
          <span className="fw-semibold">
            {filas.length} producto{filas.length === 1 ? "" : "s"} fuera del catálogo del almacén
          </span>
          <span className="text-body-secondary small d-none d-md-inline">
            — el puesto los maneja por vía externa (DIRESA / CENARES / donación); no se importan
          </span>
          <i className={`bi ms-auto ${abierto ? "bi-chevron-up" : "bi-chevron-down"}`} aria-hidden="true" />
        </button>

        {abierto && (
          <div className="mt-2" style={{ maxHeight: "40vh", overflow: "auto" }}>
            <div className="alert alert-info py-2 small mb-2" role="note">
              <i className="bi bi-info-circle me-1" aria-hidden="true" />
              No es un error: son productos con stock por lote que el catálogo central (del almacén) no
              incluye. Revísalos para decidir si alguno debe incorporarse al catálogo.
            </div>
            <table className="table table-sm table-hover mb-0 align-middle">
              <thead>
                <tr className="text-body-secondary small">
                  <th>Código</th>
                  <th>Lote</th>
                  <th>Vence</th>
                  <th className="text-end">Saldo</th>
                  {origen === "EESS" && !establecimientoCod && <th>Establecimiento</th>}
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr key={`${f.medcod}-${f.lote}-${f.establecimiento_cod ?? ""}-${i}`}>
                    <td><code>{f.medcod}</code></td>
                    <td><code>{f.lote}</code></td>
                    <td className="small">{fechaCorta(f.fecha_vcto)}</td>
                    <td className={`text-end ${f.saldo < 0 ? "text-danger fw-semibold" : ""}`}>{numero(f.saldo)}</td>
                    {origen === "EESS" && !establecimientoCod && (
                      <td className="small text-body-secondary">{f.establecimiento_nombre ?? "—"}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
