import { useRef, useState } from "react";

interface Props {
  onArchivos: (archivos: File[]) => void;
  /** Aviso para el usuario cuando algo se rechaza (p. ej. un .rar). */
  onRechazo?: (mensaje: string) => void;
  deshabilitado?: boolean;
}

function extension(nombre: string): string {
  const i = nombre.lastIndexOf(".");
  return i >= 0 ? nombre.slice(i + 1).toLowerCase() : "";
}

/** Clasifica la selección en aceptados (.dbf/.xlsx/.zip), rar y otros. */
function clasificar(lista: FileList | null): { validos: File[]; rar: boolean; otros: boolean } {
  const validos: File[] = [];
  let rar = false;
  let otros = false;
  for (const f of Array.from(lista ?? [])) {
    const ext = extension(f.name);
    if (ext === "dbf" || ext === "xlsx" || ext === "zip") validos.push(f);
    else if (ext === "rar") rar = true;
    else otros = true;
  }
  return { validos, rar, otros };
}

/**
 * Zona de arrastrar-y-soltar. Acepta DBF sueltos (uno o varios) o un .zip con
 * varios DBF adentro. Rechaza .rar (no soportado) con un aviso claro.
 */
export function ZonaSoltar({ onArchivos, onRechazo, deshabilitado = false }: Props) {
  const [encima, setEncima] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function procesar(lista: FileList | null) {
    const { validos, rar, otros } = clasificar(lista);
    if (rar) {
      onRechazo?.(
        "Los archivos .rar no se admiten. Vuelve a comprimir en formato .zip (o sube los .dbf sueltos).",
      );
    } else if (otros && !validos.length) {
      onRechazo?.("Solo se admiten archivos .dbf, .xlsx (compra CENARES) o un .zip con ellos adentro.");
    }
    if (validos.length) onArchivos(validos);
  }

  function manejarSoltar(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setEncima(false);
    if (deshabilitado) return;
    procesar(e.dataTransfer.files);
  }

  return (
    <div
      className={`card mb-3 border-2 text-center ${encima ? "border-primary bg-body-secondary" : ""}`}
      style={{ borderStyle: "dashed", cursor: deshabilitado ? "not-allowed" : "pointer", opacity: deshabilitado ? 0.6 : 1 }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!deshabilitado) setEncima(true);
      }}
      onDragLeave={() => setEncima(false)}
      onDrop={manejarSoltar}
      onClick={() => !deshabilitado && inputRef.current?.click()}
      role="button"
      aria-disabled={deshabilitado || undefined}
    >
      <div className="card-body py-5">
        <i className="bi bi-cloud-arrow-up fs-1 text-primary d-block mb-2" aria-hidden="true" />
        <p className="mb-1 fw-semibold">Arrastra archivos .dbf, .xlsx o un .zip con varios</p>
        <p className="text-body-secondary small mb-0">
          o haz clic para seleccionarlos · DBF (ICI, stock, catálogo), .xlsx (compra CENARES) o un ZIP
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".dbf,.DBF,.zip,.ZIP,.xlsx,.XLSX"
          multiple
          className="d-none"
          onChange={(e) => {
            procesar(e.target.files);
            e.target.value = ""; // permite re-seleccionar el mismo archivo
          }}
        />
      </div>
    </div>
  );
}
