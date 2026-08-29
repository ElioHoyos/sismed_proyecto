import { useNavegacion, type Pagina } from "../../navegacion";

interface ItemNav {
  etiqueta: string;
  icono: string;
  pagina?: Pagina;
  proximamente?: boolean;
}

const ITEMS_NAV: ItemNav[] = [
  { etiqueta: "Disponibilidad", icono: "bi-clipboard-data", pagina: "disponibilidad" },
  { etiqueta: "Consolidado de Red", icono: "bi-diagram-3", pagina: "consolidado" },
  { etiqueta: "Carga de archivos", icono: "bi-upload", pagina: "carga" },
  { etiqueta: "Stock", icono: "bi-box-seam", pagina: "stock" },
  { etiqueta: "Vencimientos", icono: "bi-calendar-x", pagina: "vencimientos" },
  { etiqueta: "Historial de correcciones", icono: "bi-clock-history", pagina: "historial" },
  { etiqueta: "Movimientos (kardex)", icono: "bi-arrow-left-right", pagina: "movimientos" },
  { etiqueta: "Requisición", icono: "bi-cart-check", proximamente: true },
  { etiqueta: "Tablero", icono: "bi-graph-up", proximamente: true },
];

export function Sidebar() {
  const { pagina, navegar } = useNavegacion();

  return (
    <aside className="app-sidebar bg-body-secondary shadow" data-bs-theme="dark">
      <div className="sidebar-brand">
        <a href="#" className="brand-link" onClick={(e) => e.preventDefault()}>
          <i className="bi bi-capsule-pill brand-image opacity-75 fs-4 ms-2" aria-hidden="true" />
          <span className="brand-text fw-light">Red Coronel Portillo</span>
        </a>
      </div>

      <div className="sidebar-wrapper">
        <nav className="mt-2">
          <ul className="nav sidebar-menu flex-column" role="navigation" aria-label="Navegación principal">
            {ITEMS_NAV.map((item) => {
              const activo = item.pagina === pagina;
              return (
                <li className="nav-item" key={item.etiqueta}>
                  <a
                    href="#"
                    className={`nav-link${activo ? " active" : ""}${item.proximamente ? " disabled" : ""}`}
                    aria-current={activo ? "page" : undefined}
                    aria-disabled={item.proximamente || undefined}
                    onClick={(e) => {
                      e.preventDefault();
                      if (item.pagina && !item.proximamente) navegar(item.pagina);
                    }}
                  >
                    <i className={`nav-icon bi ${item.icono}`} aria-hidden="true" />
                    <p>
                      {item.etiqueta}
                      {item.proximamente && (
                        <span className="badge text-bg-secondary ms-2">Próximamente</span>
                      )}
                    </p>
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </aside>
  );
}
