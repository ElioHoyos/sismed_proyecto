import { useEffect, useState } from "react";
import { obtenerCompraCentralizada } from "../services/api";
import type { CompraRegistro } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  anio: number | null;
  aniosDisponibles: number[];
  /** Código SISMED (= producto.medcod) → registro de compra. */
  mapa: Map<string, CompraRegistro>;
}

const VACIO: Estado = { cargando: false, error: null, anio: null, aniosDisponibles: [], mapa: new Map() };

/** Estado de compra CENARES. Solo consulta cuando `activo`. Al cambiar el año
 * (o activarse) reconsulta. */
export function useCompraCentralizada(anio: number | null, activo: boolean): Estado {
  const [estado, setEstado] = useState<Estado>(VACIO);

  useEffect(() => {
    if (!activo) {
      setEstado(VACIO);
      return;
    }
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerCompraCentralizada(anio ?? undefined)
      .then((r) => {
        if (!vigente) return;
        setEstado({
          cargando: false,
          error: null,
          anio: r.anio,
          aniosDisponibles: r.anios_disponibles,
          mapa: new Map(r.registros.map((reg) => [reg.codigo_sismed, reg])),
        });
      })
      .catch((error: unknown) => {
        if (!vigente) return;
        setEstado({ ...VACIO, error: error instanceof Error ? error.message : "Error desconocido" });
      });

    return () => {
      vigente = false;
    };
  }, [anio, activo]);

  return estado;
}
