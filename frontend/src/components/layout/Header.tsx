interface Props {
  sidebarColapsado: boolean;
  onToggleSidebar: () => void;
}

/** Toggle del sidebar manejado con estado de React (ver AppLayout) — no
 * usa data-lte-toggle porque eso depende del JS propio de AdminLTE. */
export function Header({ sidebarColapsado, onToggleSidebar }: Props) {
  return (
    <nav className="app-header navbar navbar-expand bg-body">
      <div className="container-fluid">
        <ul className="navbar-nav">
          <li className="nav-item">
            <button
              type="button"
              className="nav-link border-0 bg-transparent"
              onClick={onToggleSidebar}
              aria-pressed={sidebarColapsado}
              aria-label={sidebarColapsado ? "Expandir menú" : "Colapsar menú"}
            >
              <i className="bi bi-list" aria-hidden="true" />
            </button>
          </li>
          <li className="nav-item d-none d-md-block">
            <span className="nav-link disabled">
              Sistema de Gestión de Medicamentos
            </span>
          </li>
        </ul>
      </div>
    </nav>
  );
}
