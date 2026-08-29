import { useCallback, useEffect, useState } from "react";
import { obtenerStock } from "../services/api";
import type { OrigenStock, StockRow } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  filas: StockRow[];
  porLote: boolean; // true = filas por lote (almacén, o EESS con stock por lote)
}

/** Stock unificado según el filtro (almacén o establecimiento). Reconsulta al
 * cambiar cualquier parámetro. `porLote` indica si la respuesta viene por lote
 * (almacén o un puesto que aportó MSTKALMDE) o por producto (solo ICI). */
export function useStock(params: {
  origen: OrigenStock;
  establecimientoCod: string;
  soloNegativos: boolean;
  tipo: string;
  financiamiento: string;
  medest: string;
}): Estado & { recargar: () => void } {
  const [estado, setEstado] = useState<Estado>({ cargando: true, error: null, filas: [], porLote: true });
  const [nonce, setNonce] = useState(0);
  const { origen, establecimientoCod, soloNegativos, tipo, financiamiento, medest } = params;

  /** Reconsulta sin cambiar los filtros (p. ej. tras marcar un check de revisión). */
  const recargar = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerStock({ origen, establecimientoCod, soloNegativos, tipo, financiamiento, medest })
      .then((r) => {
        if (vigente) setEstado({ cargando: false, error: null, filas: r.resultados, porLote: r.por_lote });
      })
      .catch((error: unknown) => {
        if (vigente)
          setEstado({
            cargando: false,
            error: error instanceof Error ? error.message : "Error desconocido",
            filas: [],
            porLote: origen === "ALMACEN",
          });
      });

    return () => {
      vigente = false;
    };
  }, [origen, establecimientoCod, soloNegativos, tipo, financiamiento, medest, nonce]);

  return { ...estado, recargar };
}
