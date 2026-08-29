export interface OpcionPill {
  value: string;
  label: string;
  color?: string; // color sólido cuando está activo (para situaciones)
}

interface Props {
  label: string;
  opciones: OpcionPill[];
  valor: string; // "" = Todos
  onChange: (valor: string) => void;
  /** Agrega una pill "Todos" (value ""). Por defecto sí. */
  incluirTodos?: boolean;
  etiquetaTodos?: string;
}

/** Filtro de pocas opciones como grupo de "pills": un clic, sin abrir menú, y el
 * estado activo se ve de inmediato. Reemplaza a los <select> nativos. */
export function GrupoPills({
  label,
  opciones,
  valor,
  onChange,
  incluirTodos = true,
  etiquetaTodos = "Todos",
}: Props) {
  const todas: OpcionPill[] = incluirTodos ? [{ value: "", label: etiquetaTodos }, ...opciones] : opciones;

  return (
    <div>
      <div className="form-label mb-1">{label}</div>
      <div className="d-flex flex-wrap gap-1" role="group" aria-label={label}>
        {todas.map((o) => {
          const activo = valor === o.value;
          const estilo =
            activo && o.color
              ? { backgroundColor: o.color, borderColor: o.color, color: "#fff" }
              : undefined;
          return (
            <button
              key={o.value || "__todos"}
              type="button"
              className={`btn btn-sm rounded-pill ${
                activo ? (o.color ? "btn" : "btn-primary") : "btn-outline-secondary"
              }`}
              style={estilo}
              aria-pressed={activo}
              onClick={() => onChange(o.value)}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
