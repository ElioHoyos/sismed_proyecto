import { useState, type ReactNode } from "react";
import { NavContext, type FiltrosIniciales, type Pagina } from "./navegacion";
import { TablaMaestraPage } from "./pages/TablaMaestraPage";
import { ConsolidadoRedPage } from "./pages/ConsolidadoRedPage";
import { CargaPage } from "./pages/CargaPage";
import { StockPage } from "./pages/StockPage";
import { VencimientosPage } from "./pages/VencimientosPage";
import { HistorialPage } from "./pages/HistorialPage";
import { MovimientosPage } from "./pages/MovimientosPage";
import { AsistenteChat } from "./components/asistente/AsistenteChat";

const PAGINAS: Record<Pagina, ReactNode> = {
  disponibilidad: <TablaMaestraPage />,
  consolidado: <ConsolidadoRedPage />,
  carga: <CargaPage />,
  stock: <StockPage />,
  vencimientos: <VencimientosPage />,
  historial: <HistorialPage />,
  movimientos: <MovimientosPage />,
};

export function App() {
  const [pagina, setPagina] = useState<Pagina>("disponibilidad");
  const [filtrosIniciales, setFiltrosIniciales] = useState<FiltrosIniciales | undefined>();

  function navegar(destino: Pagina, filtros?: FiltrosIniciales) {
    setPagina(destino);
    setFiltrosIniciales(filtros); // undefined desde el sidebar → limpia
  }

  return (
    <NavContext.Provider value={{ pagina, navegar, filtrosIniciales }}>
      {PAGINAS[pagina]}
      <AsistenteChat />
    </NavContext.Provider>
  );
}
