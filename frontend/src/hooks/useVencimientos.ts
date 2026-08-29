import { useEffect, useState } from "react";
import { obtenerVencimientos } from "../services/api";
import type { FuenteVencimiento, VencimientoRow } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  hoy: string | null;
  filas: VencimientoRow[];
}

/** Vencimientos por lote (contra la fecha actual, en el backend): del almacén
 * (fuente ALMACEN) o de los establecimientos con stock por lote (fuente EESS).
 * Los filtros se aplican en el backend (refetch). */
export function useVencimientos(params: {
  fuente: FuenteVencimiento;
  establecimientoCod: string;
  tipo: string;
  financiamiento: string;
  medest: string;
}): Estado {
  const [estado, setEstado] = useState<Estado>({
    cargando: true,
    error: null,
    hoy: null,
    filas: [],
  });
  const { fuente, establecimientoCod, tipo, financiamiento, medest } = params;

  useEffect(() => {
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerVencimientos({ fuente, establecimientoCod, tipo, financiamiento, medest })
      .then((r) => {
        if (vigente)
          setEstado({ cargando: false, error: null, hoy: r.hoy, filas: r.resultados });
      })
      .catch((error: unknown) => {
        if (vigente)
          setEstado({
            cargando: false,
            error: error instanceof Error ? error.message : "Error desconocido",
            hoy: null,
            filas: [],
          });
      });

    return () => {
      vigente = false;
    };
  }, [fuente, establecimientoCod, tipo, financiamiento, medest]);

  return estado;
}
