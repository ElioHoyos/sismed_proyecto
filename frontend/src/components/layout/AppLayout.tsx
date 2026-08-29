import { useEffect, useState, type ReactNode } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

interface Props {
  titulo: string;
  children: ReactNode;
}

/**
 * Layout de AdminLTE reimplementado en React: solo se usan las clases
 * CSS (app-wrapper/app-header/app-sidebar/app-main). El colapso del
 * sidebar es la única interactividad que AdminLTE resuelve con JS
 * propio (consulta el DOM una sola vez al cargar, no es compatible con
 * una SPA) — acá se reemplaza por un simple toggle de clase en <body>,
 * que es exactamente lo que ese JS hacía.
 */
export function AppLayout({ titulo, children }: Props) {
  const [sidebarColapsado, setSidebarColapsado] = useState(false);

  useEffect(() => {
    document.body.classList.toggle("sidebar-collapse", sidebarColapsado);
  }, [sidebarColapsado]);

  useEffect(() => {
    document.body.classList.add("layout-fixed", "sidebar-expand-lg", "bg-body-tertiary");
    return () => {
      document.body.classList.remove(
        "layout-fixed",
        "sidebar-expand-lg",
        "bg-body-tertiary",
        "sidebar-collapse",
      );
    };
  }, []);

  return (
    <div className="app-wrapper">
      <Header
        sidebarColapsado={sidebarColapsado}
        onToggleSidebar={() => setSidebarColapsado((valor) => !valor)}
      />
      <Sidebar />
      <main className="app-main">
        <div className="app-content-header">
          <div className="container-fluid">
            <div className="row">
              <div className="col-sm-12">
                <h3 className="mb-0">{titulo}</h3>
              </div>
            </div>
          </div>
        </div>
        <div className="app-content">
          <div className="container-fluid">{children}</div>
        </div>
      </main>
      <footer className="app-footer">
        <div className="float-end d-none d-sm-inline">Red de Salud Coronel Portillo</div>
        <strong>Sistema de Gestión de Medicamentos</strong>
      </footer>
    </div>
  );
}
