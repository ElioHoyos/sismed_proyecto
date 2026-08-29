import { useEffect, useRef, useState } from "react";

type Formato = "xlsx" | "pdf";

interface Props {
  /** Dispara la descarga en el formato elegido. Debe lanzar si falla. */
  onExportar: (formato: Formato) => Promise<void>;
  deshabilitado?: boolean;
}

/** Botón de descarga con menú Excel / PDF y spinner mientras el backend genera
 * el archivo (un export de miles de filas toma unos segundos). */
export function BotonExportar({ onExportar, deshabilitado = false }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [generando, setGenerando] = useState<Formato | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    function alClic(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAbierto(false);
    }
    document.addEventListener("mousedown", alClic);
    return () => document.removeEventListener("mousedown", alClic);
  }, [abierto]);

  async function exportar(formato: Formato) {
    setAbierto(false);
    setError(null);
    setGenerando(formato);
    try {
      await onExportar(formato);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al exportar");
    } finally {
      setGenerando(null);
    }
  }

  const ocupado = generando !== null;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        type="button"
        className="btn btn-outline-success btn-sm"
        onClick={() => setAbierto((v) => !v)}
        disabled={deshabilitado || ocupado}
        aria-haspopup="menu"
        aria-expanded={abierto}
      >
        {ocupado ? (
          <>
            <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true" />
            Generando {generando === "pdf" ? "PDF" : "Excel"}…
          </>
        ) : (
          <>
            <i className="bi bi-download me-1" aria-hidden="true" />
            Exportar
          </>
        )}
      </button>

      {abierto && (
        <div className="card shadow position-absolute mt-1" style={{ zIndex: 1055, right: 0, minWidth: 170 }} role="menu">
          <ul className="list-group list-group-flush mb-0">
            <li>
              <button type="button" className="list-group-item list-group-item-action d-flex align-items-center gap-2" onClick={() => exportar("xlsx")}>
                <i className="bi bi-file-earmark-spreadsheet text-success" aria-hidden="true" />
                Excel (.xlsx)
              </button>
            </li>
            <li>
              <button type="button" className="list-group-item list-group-item-action d-flex align-items-center gap-2" onClick={() => exportar("pdf")}>
                <i className="bi bi-file-earmark-pdf text-danger" aria-hidden="true" />
                PDF (imprimir)
              </button>
            </li>
          </ul>
        </div>
      )}

      {error && (
        <div className="position-absolute mt-1 alert alert-danger py-1 px-2 small mb-0" style={{ zIndex: 1055, right: 0, minWidth: 220 }} role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
