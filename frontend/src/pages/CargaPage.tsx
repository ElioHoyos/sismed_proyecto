import { useMemo, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { useNavegacion, type Pagina } from "../navegacion";
import { ZonaSoltar } from "../components/ici/ZonaSoltar";
import { TablaPreview } from "../components/ici/TablaPreview";
import { ResumenLote } from "../components/ici/ResumenLote";
import { ProgresoLote, type EstadoProgreso, type FilaProgreso } from "../components/ici/ProgresoLote";
import { useEstablecimientos } from "../hooks/useEstablecimientos";
import { importarLoteStream, previsualizar } from "../services/api";
import type { PreviewArchivo, ResumenLoteImportacion } from "../services/types";

/** Una fila del paso 1: un DBF (suelto o de un ZIP), con su tipo detectado y,
 * solo para los ICI, el establecimiento asignado. */
export interface EntradaArchivo {
  archivo: string; // basename, clave única en el lote
  preview: PreviewArchivo;
  codigoAsignado: string; // cod_2000 (solo ICI); "" si sin asignar
}

function periodoActual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function mensajeError(error: unknown): string {
  return error instanceof Error ? error.message : "Error desconocido";
}

function mismaSubida(a: File, b: File): boolean {
  return a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;
}

export function CargaPage() {
  const { establecimientos, error: errorEst } = useEstablecimientos();
  const { navegar } = useNavegacion();

  const [periodo, setPeriodo] = useState<string>(periodoActual);
  const [archivosCrudos, setArchivosCrudos] = useState<File[]>([]);
  const [entradas, setEntradas] = useState<EntradaArchivo[]>([]);
  const [previsualizando, setPrevisualizando] = useState(false);
  const [importando, setImportando] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResumenLoteImportacion | null>(null);
  // Progreso en vivo del lote (archivo por archivo) mientras se importa.
  const [progreso, setProgreso] = useState<FilaProgreso[]>([]);
  const [recalculando, setRecalculando] = useState(false);

  const nombrePorCod = useMemo(
    () => new Map(establecimientos.map((e) => [e.cod_2000, e.nombre])),
    [establecimientos],
  );

  async function previsualizarTodos(crudos: File[]) {
    if (!crudos.length) {
      setEntradas([]);
      return;
    }
    setPrevisualizando(true);
    setErrorMsg(null);
    try {
      const respuesta = await previsualizar(crudos);
      setEntradas((prev) => {
        const codPrevio = new Map(prev.map((e) => [e.archivo, e.codigoAsignado]));
        return respuesta.archivos.map((p) => ({
          archivo: p.archivo,
          preview: p,
          codigoAsignado: codPrevio.has(p.archivo)
            ? (codPrevio.get(p.archivo) as string)
            : p.tipo === "ICI" && p.establecimiento && p.confianza !== "no_encontrado"
              ? p.establecimiento.cod_2000
              : "",
        }));
      });
    } catch (error: unknown) {
      setErrorMsg(mensajeError(error));
    } finally {
      setPrevisualizando(false);
    }
  }

  function agregarArchivos(files: File[]) {
    const nuevos = files.filter((f) => !archivosCrudos.some((c) => mismaSubida(c, f)));
    if (!nuevos.length) return;
    const todos = [...archivosCrudos, ...nuevos];
    setArchivosCrudos(todos);
    void previsualizarTodos(todos);
  }

  function cambiarEstablecimiento(archivo: string, cod2000: string) {
    setEntradas((prev) =>
      prev.map((e) => (e.archivo === archivo ? { ...e, codigoAsignado: cod2000 } : e)),
    );
  }

  function quitar(archivo: string) {
    setEntradas((prev) => prev.filter((e) => e.archivo !== archivo));
    setArchivosCrudos((prev) =>
      prev.filter((c) => !(c.name === archivo && c.name.toLowerCase().endsWith(".dbf"))),
    );
  }

  const importables = entradas.filter((e) => !e.preview.error && e.preview.tipo !== "DESCONOCIDO");
  const iciSinAsignar = importables.filter(
    (e) => e.preview.tipo === "ICI" && e.codigoAsignado === "",
  ).length;
  const puedeImportar =
    Boolean(periodo) && importables.length > 0 && iciSinAsignar === 0 && !previsualizando && !importando;

  async function importar() {
    const asignaciones: Record<string, string> = {};
    for (const e of entradas) {
      if (e.preview.tipo === "ICI" && !e.preview.error && e.codigoAsignado) {
        asignaciones[e.archivo] = e.codigoAsignado;
      }
    }
    if (!importables.length || !periodo) return;

    setImportando(true);
    setErrorMsg(null);
    setResultado(null);
    setRecalculando(false);
    setProgreso([]);
    try {
      await importarLoteStream({ archivos: archivosCrudos, asignaciones, periodo }, (ev) => {
        if (ev.evento === "plan") {
          setProgreso(ev.archivos.map((a) => ({ archivo: a.archivo, tipo: a.tipo, estado: "en_cola" })));
        } else if (ev.evento === "archivo_inicio") {
          setProgreso((prev) =>
            prev.map((f) => (f.archivo === ev.archivo ? { ...f, estado: "procesando" } : f)),
          );
        } else if (ev.evento === "archivo_fin") {
          const r = ev.resultado;
          setProgreso((prev) =>
            prev.map((f) => (f.archivo === r.archivo ? { ...f, estado: r.estado as EstadoProgreso, resultado: r } : f)),
          );
        } else if (ev.evento === "recalculo_inicio") {
          setRecalculando(true);
        } else if (ev.evento === "fin") {
          setRecalculando(false);
          setResultado(ev.resumen);
        } else if (ev.evento === "error") {
          setErrorMsg(ev.error);
        }
      });
    } catch (error: unknown) {
      setErrorMsg(mensajeError(error));
    } finally {
      setImportando(false);
      setRecalculando(false);
    }
  }

  function reiniciarProgreso() {
    setProgreso([]);
    setErrorMsg(null);
    setRecalculando(false);
  }

  function nuevaCarga() {
    setArchivosCrudos([]);
    setEntradas([]);
    setResultado(null);
    setErrorMsg(null);
    setProgreso([]);
    setRecalculando(false);
  }

  const hayIci = importables.some((e) => e.preview.tipo === "ICI");
  const mostrarResultado = resultado !== null;
  const mostrarProgreso = !mostrarResultado && progreso.length > 0;
  const fase: 1 | 2 = mostrarResultado ? 2 : 1;

  return (
    <AppLayout titulo="Carga de archivos">
      <Pasos fase={fase} />

      {errorEst && (
        <div className="alert alert-warning" role="alert">
          No se pudo cargar el catálogo de establecimientos: {errorEst}. Los selectores de
          corrección estarán vacíos.
        </div>
      )}

      {mostrarProgreso ? (
        <>
          {errorMsg && (
            <div className="alert alert-danger d-flex align-items-start gap-2" role="alert">
              <i className="bi bi-exclamation-octagon-fill mt-1" aria-hidden="true" />
              <span>{errorMsg}</span>
            </div>
          )}
          <ProgresoLote filas={progreso} recalculando={recalculando} terminado={!importando} />
          {importando ? (
            <p className="text-body-secondary small">
              <i className="bi bi-info-circle me-1" aria-hidden="true" />
              Importando en vivo… no cierres esta pestaña.
            </p>
          ) : (
            <button type="button" className="btn btn-outline-secondary" onClick={reiniciarProgreso}>
              <i className="bi bi-arrow-left me-1" aria-hidden="true" />
              Volver
            </button>
          )}
        </>
      ) : fase === 1 ? (
        <>
          <div className="card mb-3">
            <div className="card-body">
              <div className="row g-3 align-items-end">
                <div className="col-sm-4 col-md-3">
                  <label className="form-label" htmlFor="periodo-lote">
                    Periodo (mes de cierre)
                  </label>
                  <input
                    id="periodo-lote"
                    type="month"
                    className="form-control"
                    value={periodo}
                    onChange={(e) => setPeriodo(e.target.value)}
                  />
                </div>
                <div className="col">
                  <p className="text-body-secondary small mb-0">
                    Sube los DBF que tengas: el sistema detecta el tipo de cada uno (ICI, stock por
                    lote o catálogo) y lo enruta solo. El stock por lote (MSTKALMDE) puede ser del{" "}
                    <strong>almacén</strong> o de un <strong>establecimiento</strong> con SISMED propio;
                    se reconoce por el ALMCOD y se muestra abajo. El periodo aplica a los archivos{" "}
                    <strong>ICI</strong> (y como fecha de la foto del stock); el catálogo no lo usa.
                    Solo los ICI necesitan que confirmes el establecimiento.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <ZonaSoltar onArchivos={agregarArchivos} onRechazo={setErrorMsg} deshabilitado={importando} />

          {errorMsg && (
            <div className="alert alert-danger d-flex align-items-start gap-2" role="alert">
              <i className="bi bi-exclamation-octagon-fill mt-1" aria-hidden="true" />
              <span>{errorMsg}</span>
            </div>
          )}

          {previsualizando && (
            <div className="alert alert-info d-flex align-items-center gap-2" role="status">
              <span className="spinner-border spinner-border-sm" aria-hidden="true" />
              Analizando archivos…
            </div>
          )}

          {entradas.length > 0 && (
            <>
              <TablaPreview
                entradas={entradas}
                establecimientos={establecimientos}
                onCambiarEstablecimiento={cambiarEstablecimiento}
                onQuitar={quitar}
              />

              <div className="d-flex flex-wrap align-items-center gap-3">
                <button type="button" className="btn btn-primary" onClick={importar} disabled={!puedeImportar}>
                  {importando ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                      Importando…
                    </>
                  ) : (
                    <>
                      <i className="bi bi-database-add me-1" aria-hidden="true" />
                      Importar {importables.length} archivo{importables.length === 1 ? "" : "s"}
                    </>
                  )}
                </button>

                <button type="button" className="btn btn-outline-secondary" onClick={nuevaCarga} disabled={importando}>
                  Limpiar lote
                </button>

                <span className="text-body-secondary small">
                  {importables.length} para importar
                  {hayIci && iciSinAsignar > 0 && (
                    <span className="text-warning"> · {iciSinAsignar} ICI sin establecimiento</span>
                  )}
                </span>
              </div>

              {importando && (
                <div className="progress mt-3" role="progressbar" aria-label="Importando lote">
                  <div className="progress-bar progress-bar-striped progress-bar-animated w-100" />
                </div>
              )}
            </>
          )}
        </>
      ) : (
        resultado && (
          <ResumenLote
            resumen={resultado}
            nombrePorCod={nombrePorCod}
            onNuevaCarga={nuevaCarga}
            onIrAModulo={(pagina) => navegar(pagina as Pagina)}
          />
        )
      )}
    </AppLayout>
  );
}

function Pasos({ fase }: { fase: 1 | 2 }) {
  const pasos = [
    { n: 1, label: "Seleccionar y previsualizar" },
    { n: 2, label: "Importar y ver resultado" },
  ];
  return (
    <ol className="list-unstyled d-flex flex-wrap gap-2 mb-3">
      {pasos.map((p) => {
        const activo = p.n === fase;
        const hecho = p.n < fase;
        return (
          <li
            key={p.n}
            className={`badge rounded-pill px-3 py-2 ${
              activo ? "text-bg-primary" : hecho ? "text-bg-success" : "text-bg-light"
            }`}
          >
            <span className="me-1">
              {hecho ? <i className="bi bi-check-lg" aria-hidden="true" /> : `Paso ${p.n}`}
            </span>
            {p.label}
          </li>
        );
      })}
    </ol>
  );
}
