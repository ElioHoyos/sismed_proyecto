import { useEffect, useRef, useState } from "react";

export interface OpcionBuscable {
  value: string;
  label: string;
}

interface Props {
  label: string;
  opciones: OpcionBuscable[];
  valor: string; // "" = ninguno
  onChange: (valor: string) => void;
  placeholder?: string;
  etiquetaTodos?: string; // texto de la opción vacía
}

/** Desplegable con buscador interno — para listas largas (89 establecimientos).
 * Se cierra al hacer clic fuera o con Escape. */
export function SelectorBuscable({
  label,
  opciones,
  valor,
  onChange,
  placeholder = "Buscar…",
  etiquetaTodos = "— Todos —",
}: Props) {
  const [abierto, setAbierto] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    function alClic(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setAbierto(false);
    }
    function alEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setAbierto(false);
    }
    document.addEventListener("mousedown", alClic);
    document.addEventListener("keydown", alEscape);
    return () => {
      document.removeEventListener("mousedown", alClic);
      document.removeEventListener("keydown", alEscape);
    };
  }, [abierto]);

  const seleccionado = opciones.find((o) => o.value === valor);
  const ql = q.trim().toLowerCase();
  const filtradas = ql ? opciones.filter((o) => o.label.toLowerCase().includes(ql)) : opciones;

  function elegir(v: string) {
    onChange(v);
    setAbierto(false);
    setQ("");
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <div className="form-label mb-1">{label}</div>
      <button
        type="button"
        className="form-select text-start"
        onClick={() => setAbierto((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={abierto}
      >
        <span className={seleccionado ? "" : "text-body-secondary"}>
          {seleccionado ? seleccionado.label : etiquetaTodos}
        </span>
      </button>

      {abierto && (
        <div
          className="card shadow position-absolute w-100 mt-1"
          style={{ zIndex: 1055, maxHeight: 320, minWidth: 260 }}
        >
          <div className="p-2 border-bottom">
            <input
              type="search"
              className="form-control form-control-sm"
              placeholder={placeholder}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              autoFocus
            />
          </div>
          <ul className="list-group list-group-flush overflow-auto mb-0" style={{ maxHeight: 260 }} role="listbox">
            <li>
              <button
                type="button"
                className={`list-group-item list-group-item-action ${valor === "" ? "active" : ""}`}
                onClick={() => elegir("")}
              >
                {etiquetaTodos}
              </button>
            </li>
            {filtradas.map((o) => (
              <li key={o.value}>
                <button
                  type="button"
                  className={`list-group-item list-group-item-action ${o.value === valor ? "active" : ""}`}
                  onClick={() => elegir(o.value)}
                >
                  {o.label}
                </button>
              </li>
            ))}
            {filtradas.length === 0 && (
              <li className="list-group-item text-body-secondary small">Sin coincidencias.</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
