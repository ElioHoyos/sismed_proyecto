import { useCallback, useEffect, useMemo, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { useNavegacion } from "../navegacion";
import { FiltrosBarra, type EstablecimientoOpcion } from "../components/FiltrosBarra";
import { ChipsActivos, type ChipActivo } from "../components/filtros/ChipsActivos";
import { BotonExportar } from "../components/BotonExportar";
import { descargarExport } from "../services/api";
import { ResumenSituacionRed } from "../components/ResumenSituacionRed";
import { ResumenSituacionFiltrado, type ItemSituacion } from "../components/ResumenSituacionFiltrado";
import { TablaMaestra } from "../components/TablaMaestra";
import { useDisponibilidadEstablecimiento } from "../hooks/useDisponibilidadEstablecimiento";
import { useDisponibilidadRed } from "../hooks/useDisponibilidadRed";
import { useResumenSituacionRed } from "../hooks/useResumenSituacionRed";
import { SITUACION_META, SITUACION_ORDEN } from "../services/situacion";
import { SIGNIFICADO_MEDEST, SIGNIFICADO_MEDPET, SIGNIFICADO_MEDTIP } from "../services/clasificacion";
import type { Situacion, Vista } from "../services/types";

export function TablaMaestraPage() {
  const [vista, setVista] = useState<Vista>("establecimiento");
  const [periodoInput, setPeriodoInput] = useState<string>("");
  const [establecimientoCod, setEstablecimientoCod] = useState<string>("");
  const [situacionFiltro, setSituacionFiltro] = useState<Situacion | "">("");
  const [tipoFiltro, setTipoFiltro] = useState<string>(""); // MEDTIP: "" | "M" | "I"
  const [petitorioFiltro, setPetitorioFiltro] = useState<string>(""); // MEDPET: "" | "P" | "_"
  const [medestFiltro, setMedestFiltro] = useState<string>(""); // MEDEST: "" | "S" | "_" | "E"
  const [busqueda, setBusqueda] = useState<string>("");
  const [vistaCompacta, setVistaCompacta] = useState<boolean>(false);

  // Filtros pre-aplicados al llegar desde el asistente ("Ver en el módulo").
  const { filtrosIniciales } = useNavegacion();
  useEffect(() => {
    if (!filtrosIniciales) return;
    if (filtrosIniciales.vista) setVista(filtrosIniciales.vista as Vista);
    if (filtrosIniciales.situacion) setSituacionFiltro(filtrosIniciales.situacion as Situacion);
    setTipoFiltro(filtrosIniciales.tipo ?? "");
    setPetitorioFiltro(filtrosIniciales.financiamiento ?? "");
    setMedestFiltro(filtrosIniciales.medest ?? "");
    setBusqueda(filtrosIniciales.busqueda ?? "");
  }, [filtrosIniciales]);

  const disponibilidadEst = useDisponibilidadEstablecimiento(periodoInput || undefined);
  const disponibilidadRed = useDisponibilidadRed(periodoInput || undefined);
  const resumenRed = useResumenSituacionRed(periodoInput || undefined);

  // El periodo que muestran los selectores es el que confirmó el backend
  // (más reciente por defecto), no el que el usuario escribió a medias.
  const periodoConfirmado = disponibilidadEst.periodo ?? disponibilidadRed.periodo ?? "";

  const establecimientos = useMemo<EstablecimientoOpcion[]>(() => {
    const vistos = new Map<string, string>();
    for (const fila of disponibilidadEst.filas) {
      vistos.set(fila.establecimiento_cod, fila.establecimiento_nombre);
    }
    return [...vistos.entries()]
      .map(([cod, nombre]) => ({ cod, nombre }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }, [disponibilidadEst.filas]);

  const busquedaNormalizada = busqueda.trim().toLowerCase();

  const coincideClasificacion = useCallback(
    (f: { situacion: Situacion; medtip: string | null; medpet: string | null; medest: string | null }) =>
      (!situacionFiltro || f.situacion === situacionFiltro) &&
      (!tipoFiltro || f.medtip === tipoFiltro) &&
      (!petitorioFiltro || f.medpet === petitorioFiltro) &&
      (!medestFiltro || f.medest === medestFiltro),
    [situacionFiltro, tipoFiltro, petitorioFiltro, medestFiltro],
  );

  const coincideBusqueda = useCallback(
    (f: { producto_nombre: string; producto_cod: string }) =>
      !busquedaNormalizada ||
      f.producto_nombre.toLowerCase().includes(busquedaNormalizada) ||
      f.producto_cod.toLowerCase().includes(busquedaNormalizada),
    [busquedaNormalizada],
  );

  const filasEstablecimiento = useMemo(() => {
    if (!establecimientoCod) return [];
    return disponibilidadEst.filas
      .filter((f) => f.establecimiento_cod === establecimientoCod)
      .filter(coincideClasificacion)
      .filter(coincideBusqueda);
  }, [disponibilidadEst.filas, establecimientoCod, coincideClasificacion, coincideBusqueda]);

  const filasRed = useMemo(() => {
    return disponibilidadRed.filas.filter(coincideClasificacion).filter(coincideBusqueda);
  }, [disponibilidadRed.filas, coincideClasificacion, coincideBusqueda]);

  const vistaEstablecimientoSinSeleccion = vista === "establecimiento" && !establecimientoCod;
  const filas = vista === "establecimiento" ? filasEstablecimiento : filasRed;

  // Desglose por situación de lo que se está viendo (reacciona a los filtros;
  // el total coincide con el contador). En red se usa la situación total (Red +
  // AEM), en establecimiento la del propio EESS — lo mismo que muestra la tabla.
  const situacionItems = useMemo<ItemSituacion[]>(() => {
    const total = filas.length;
    const conteo = new Map<Situacion, number>();
    for (const f of filas) {
      const s = vista === "red" ? f.situacion_total : f.situacion;
      conteo.set(s, (conteo.get(s) ?? 0) + 1);
    }
    return SITUACION_ORDEN.map((s) => {
      const cantidad = conteo.get(s) ?? 0;
      return { situacion: s, cantidad, porcentaje: total ? Math.round((1000 * cantidad) / total) / 10 : 0 };
    }).filter((i) => i.cantidad > 0);
  }, [filas, vista]);

  function alternarSituacion(s: Situacion) {
    setSituacionFiltro((prev) => (prev === s ? "" : s));
  }
  const cargando = vista === "establecimiento" ? disponibilidadEst.cargando : disponibilidadRed.cargando;
  const error = vista === "establecimiento" ? disponibilidadEst.error : disponibilidadRed.error;

  function limpiarFiltros() {
    setSituacionFiltro("");
    setTipoFiltro("");
    setPetitorioFiltro("");
    setMedestFiltro("");
    setBusqueda("");
    setPeriodoInput("");
  }

  const chips: ChipActivo[] = [];
  if (situacionFiltro)
    chips.push({ clave: "sit", etiqueta: `Situación: ${SITUACION_META[situacionFiltro].label}`, onQuitar: () => setSituacionFiltro("") });
  if (tipoFiltro)
    chips.push({ clave: "tipo", etiqueta: `Tipo: ${SIGNIFICADO_MEDTIP[tipoFiltro]} (${tipoFiltro})`, onQuitar: () => setTipoFiltro("") });
  if (petitorioFiltro)
    chips.push({ clave: "fin", etiqueta: `Financiamiento: ${SIGNIFICADO_MEDPET[petitorioFiltro]} (${petitorioFiltro})`, onQuitar: () => setPetitorioFiltro("") });
  if (medestFiltro)
    chips.push({ clave: "medest", etiqueta: `MEDEST: ${SIGNIFICADO_MEDEST[medestFiltro]} (${medestFiltro})`, onQuitar: () => setMedestFiltro("") });
  if (busqueda.trim())
    chips.push({ clave: "busq", etiqueta: `Buscar: "${busqueda.trim()}"`, onQuitar: () => setBusqueda("") });
  if (periodoInput)
    chips.push({ clave: "per", etiqueta: `Periodo: ${periodoInput}`, onQuitar: () => setPeriodoInput("") });

  // Al hacer clic en un estado del resumen (que es de toda la red): si ya
  // estaba activo, lo quita; si no, filtra por él y salta a la vista de red
  // para que se vean todos los productos de la red en esa situación.
  function seleccionarSituacionRed(situacion: Situacion) {
    if (situacionFiltro === situacion) {
      setSituacionFiltro("");
    } else {
      setSituacionFiltro(situacion);
      setVista("red");
    }
  }

  function exportar(formato: "xlsx" | "pdf") {
    return descargarExport("/api/disponibilidad/export", {
      formato,
      vista,
      establecimiento_cod: vista === "establecimiento" ? establecimientoCod : undefined,
      periodo: periodoConfirmado || undefined,
      situacion: situacionFiltro || undefined,
      tipo: tipoFiltro || undefined,
      financiamiento: petitorioFiltro || undefined,
      medest: medestFiltro || undefined,
      buscar: busqueda.trim() || undefined,
    });
  }

  return (
    <AppLayout titulo={`Disponibilidad — tabla maestra (periodo ${periodoConfirmado || "…"})`}>
      <ResumenSituacionRed
        cargando={resumenRed.cargando}
        error={resumenRed.error}
        totalSoporte={resumenRed.totalSoporte}
        totalSis={resumenRed.totalSis}
        soporte={resumenRed.soporte}
        sis={resumenRed.sis}
        situacionActiva={situacionFiltro}
        onSituacionSelect={seleccionarSituacionRed}
      />

      <FiltrosBarra
        vista={vista}
        onVistaChange={setVista}
        periodo={periodoInput}
        onPeriodoChange={setPeriodoInput}
        establecimientos={establecimientos}
        establecimientoCod={establecimientoCod}
        onEstablecimientoChange={setEstablecimientoCod}
        situacionFiltro={situacionFiltro}
        onSituacionChange={setSituacionFiltro}
        tipoFiltro={tipoFiltro}
        onTipoChange={setTipoFiltro}
        petitorioFiltro={petitorioFiltro}
        onPetitorioChange={setPetitorioFiltro}
        medestFiltro={medestFiltro}
        onMedestChange={setMedestFiltro}
        busqueda={busqueda}
        onBusquedaChange={setBusqueda}
        vistaCompacta={vistaCompacta}
        onVistaCompactaChange={setVistaCompacta}
      />

      <div className="d-flex justify-content-between align-items-start gap-2 flex-wrap">
        {!vistaEstablecimientoSinSeleccion ? (
          <ChipsActivos
            chips={chips}
            onLimpiar={limpiarFiltros}
            contador={`${filas.length} ${filas.length === 1 ? "producto" : "productos"}`}
            cargando={cargando}
          />
        ) : (
          <span />
        )}
        <BotonExportar onExportar={exportar} deshabilitado={vistaEstablecimientoSinSeleccion} />
      </div>

      {vista === "establecimiento" && establecimientoCod && (
        <div className="alert alert-info d-flex align-items-start gap-2 py-2 small" role="note">
          <i className="bi bi-info-circle-fill mt-1" aria-hidden="true" />
          <span>
            El stock del almacén central es compartido por toda la red: esta disponibilidad supone
            acceso al almacén completo, no que ese stock sea exclusivo de este establecimiento.
          </span>
        </div>
      )}

      {vistaEstablecimientoSinSeleccion ? (
        <div className="alert alert-secondary text-center py-5" role="status">
          <i className="bi bi-hospital fs-2 d-block mb-2" aria-hidden="true" />
          Selecciona un establecimiento arriba para ver su tabla de disponibilidad.
        </div>
      ) : (
        <>
          <ResumenSituacionFiltrado
            total={filas.length}
            items={situacionItems}
            situacionActiva={situacionFiltro}
            onSituacionSelect={alternarSituacion}
          />
          <TablaMaestra filas={filas} cargando={cargando} error={error} compacta={vistaCompacta} vista={vista} />
        </>
      )}
    </AppLayout>
  );
}
