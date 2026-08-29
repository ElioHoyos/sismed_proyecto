import { useCallback, useEffect, useState } from "react";
import { obtenerConsolidado } from "../services/api";
import type { CampoEditableCompra, ConsolidadoRow } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  periodo: string | null;
  compraAnio: number | null;
  aniosCompra: number[];
  filas: ConsolidadoRow[];
}

const INICIAL: Estado = {
  cargando: true,
  error: null,
  periodo: null,
  compraAnio: null,
  aniosCompra: [],
  filas: [],
};

/**
 * Vista consolidada de red (ICI + cálculos + CENARES). El `compraAnio` elige el
 * año de compra a cruzar. `recargar` se llama tras guardar/revertir una edición
 * para traer los valores finales del backend (incluye restaurar el valor del
 * archivo al revertir). `nonce` fuerza recargas sin cambiar los filtros.
 */
export function useConsolidado(periodo: string | undefined, compraAnio: number | undefined) {
  const [estado, setEstado] = useState<Estado>(INICIAL);
  const [nonce, setNonce] = useState(0);

  const recargar = useCallback(() => setNonce((n) => n + 1), []);

  /** Aplica la edición en memoria (optimista) para que la celda responda al
   * instante y no se pierda lo escrito si el guardado falla. `valorFinal` null
   * = revertir (se limpia local; luego `recargar` trae el valor del archivo). */
  const aplicarEdicionLocal = useCallback(
    (cod: string, campo: CampoEditableCompra, valorFinal: string | null) => {
      setEstado((s) => ({
        ...s,
        filas: s.filas.map((f) => {
          if (f.producto_cod !== cod) return f;
          const editados =
            valorFinal !== null
              ? Array.from(new Set([...f.compra.editados, campo]))
              : f.compra.editados.filter((c) => c !== campo);
          return {
            ...f,
            compra: { ...f.compra, [campo]: valorFinal, editados, sin_registro: false },
          };
        }),
      }));
    },
    [],
  );

  useEffect(() => {
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerConsolidado({ periodo, compraAnio })
      .then((r) => {
        if (!vigente) return;
        setEstado({
          cargando: false,
          error: null,
          periodo: r.periodo,
          compraAnio: r.compra_anio,
          aniosCompra: r.anios_compra,
          filas: r.resultados,
        });
      })
      .catch((error: unknown) => {
        if (!vigente) return;
        setEstado((prev) => ({
          ...prev,
          cargando: false,
          error: error instanceof Error ? error.message : "Error desconocido",
        }));
      });

    return () => {
      vigente = false;
    };
  }, [periodo, compraAnio, nonce]);

  return { ...estado, recargar, aplicarEdicionLocal };
}
