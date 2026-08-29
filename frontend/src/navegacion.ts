import { createContext, useContext } from "react";

/** Páginas de la app. Navegación mínima por estado (sin react-router): el
 * sidebar y el asistente leen/escriben este contexto. */
export type Pagina =
  | "disponibilidad"
  | "consolidado"
  | "carga"
  | "stock"
  | "vencimientos"
  | "historial"
  | "movimientos";

/** Filtros que el asistente puede pre-aplicar al llevar a una pantalla
 * ("Ver en el módulo"). Cada pantalla toma los que le apliquen. */
export interface FiltrosIniciales {
  estado?: string;
  tipo?: string;
  financiamiento?: string;
  medest?: string;
  origen?: string;
  soloNegativos?: boolean;
  establecimientoCod?: string;
  busqueda?: string;
  situacion?: string;
  vista?: string;
}

interface NavContextValue {
  pagina: Pagina;
  navegar: (pagina: Pagina, filtros?: FiltrosIniciales) => void;
  /** Filtros a aplicar en la página destino (se limpian al navegar sin ellos). */
  filtrosIniciales?: FiltrosIniciales;
}

export const NavContext = createContext<NavContextValue>({
  pagina: "disponibilidad",
  navegar: () => {},
});

export const useNavegacion = () => useContext(NavContext);
