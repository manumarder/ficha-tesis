"use client";

import { useEffect, useState, useMemo } from "react";
import {
  getAlertasTrampa,
  getHistorialProducto,
  getOfertasReales,
  getOpcionesFiltros,
  OpcionesFiltros,
  ProductoAuditado,
  PuntoHistorial,
  searchProductos,
} from "./services/api";

function precioFinal(producto: ProductoAuditado): number {
  return producto.precio_final ?? producto.precio_descuento ?? producto.precio_normal;
}

function formatoPrecio(value?: number): string {
  return value != null
    ? `$${value.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : "-";
}

function BadgeSemaforo({ semaforo, dias }: { semaforo?: string; dias?: number }) {
  if (dias != null && dias < 7) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 border border-slate-200">
        ⚪ Muestra Insuficiente (&lt;7d)
      </span>
    );
  }

  switch (semaforo) {
    case "🟢":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200">
          🟢 Oferta Real Auditada
        </span>
      );
    case "🔴":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 border border-rose-200">
          🔴 Alerta de Inflado Previo
        </span>
      );
    case "🟡":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 border border-amber-200">
          🟡 Variación Neutral
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 border border-slate-200">
          ⚪ Sin Clasificar
        </span>
      );
  }
}

function GraficoHistorial({ puntos }: { puntos: PuntoHistorial[] }) {
  if (puntos.length === 0) {
    return <p className="mt-3 text-xs text-slate-500">No hay observaciones de precio para los últimos 21 días.</p>;
  }

  const width = 640;
  const height = 190;
  const padding = { top: 14, right: 18, bottom: 34, left: 64 };
  const values = puntos.map((punto) => punto.precio_final);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || Math.max(max * 0.05, 1);
  const x = (index: number) => padding.left + (index / Math.max(puntos.length - 1, 1)) * (width - padding.left - padding.right);
  const y = (value: number) => max === min
    ? padding.top + (height - padding.top - padding.bottom) / 2
    : padding.top + ((max + range * 0.08 - value) / (range * 1.16)) * (height - padding.top - padding.bottom);
  const polyline = puntos.map((punto, index) => `${x(index)},${y(punto.precio_final)}`).join(" ");
  const formatDate = (fecha: string) => new Date(`${fecha}T00:00:00`).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });

  return (
    <div className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between px-1 pb-2">
        <p className="text-xs font-semibold text-slate-700">Precio efectivo · últimos 21 días</p>
        <p className="text-[0.65rem] text-slate-400">{puntos.length} observaciones</p>
      </div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Gráfico de evolución del precio efectivo en los últimos 21 días" className="h-48 min-w-[480px] w-full">
          {[0, 1, 2].map((tick) => {
            const value = min + (max - min) * (tick / 2);
            const yPosition = y(value);
            return (
              <g key={tick}>
                <line x1={padding.left} y1={yPosition} x2={width - padding.right} y2={yPosition} stroke="#e2e8f0" strokeDasharray="4 4" />
                <text x={padding.left - 8} y={yPosition + 4} textAnchor="end" fontSize="10" fill="#64748b">{formatoPrecio(value)}</text>
              </g>
            );
          })}
          <polyline points={polyline} fill="none" stroke="#0284c7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          {puntos.map((punto, index) => (
            <g key={`${punto.fecha}-${index}`}>
              <circle cx={x(index)} cy={y(punto.precio_final)} r="4" fill="#0284c7" stroke="white" strokeWidth="2">
                <title>{`${formatDate(punto.fecha)} · ${formatoPrecio(punto.precio_final)}`}</title>
              </circle>
            </g>
          ))}
          <text x={padding.left} y={height - 8} textAnchor="start" fontSize="10" fill="#64748b">{formatDate(puntos[0].fecha)}</text>
          <text x={width - padding.right} y={height - 8} textAnchor="end" fontSize="10" fill="#64748b">{formatDate(puntos[puntos.length - 1].fecha)}</text>
        </svg>
      </div>
      <p className="px-1 pt-1 text-[0.65rem] text-slate-400">Se muestra la última captura disponible de cada día; los días sin captura no se interpolan.</p>
    </div>
  );
}

export default function Home() {
  const [ofertasReales, setOfertasReales] = useState<ProductoAuditado[]>([]);
  const [alertasTrampa, setAlertasTrampa] = useState<ProductoAuditado[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [initialError, setInitialError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<ProductoAuditado[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [filtroOrden, setFiltroOrden] = useState<"mayor" | "menor">("mayor");
  const [isOffline, setIsOffline] = useState(false);
  const [opcionesFiltros, setOpcionesFiltros] = useState<OpcionesFiltros>({ supermercados: [], categorias: [] });
  const [filtroSupermercado, setFiltroSupermercado] = useState("");
  const [filtroCategoria, setFiltroCategoria] = useState("");
  const [historialAbierto, setHistorialAbierto] = useState<string | null>(null);
  const [historiales, setHistoriales] = useState<Record<string, PuntoHistorial[]>>({ });
  const [historialCargando, setHistorialCargando] = useState<string | null>(null);
  const [historialError, setHistorialError] = useState<string | null>(null);

  useEffect(() => {
    getOpcionesFiltros()
      .then(setOpcionesFiltros)
      .catch(() => setOpcionesFiltros({ supermercados: [], categorias: [] }));
  }, []);

  useEffect(() => {
    let active = true;
    async function loadInitialData() {
      try {
        const filtros = { supermercado: filtroSupermercado, categoria: filtroCategoria };
        const [reales, trampas] = await Promise.all([getOfertasReales(filtros), getAlertasTrampa(filtros)]);
        if (!active) return;
        setOfertasReales(reales);
        setAlertasTrampa(trampas);
        setIsOffline(false);
        setInitialError(null);
      } catch {
        if (!active) return;
        setIsOffline(true);
        setInitialError("No se pudo cargar la auditoría. Verificá que la API esté activa e intentá recargar.");
      } finally {
        if (active) setInitialLoading(false);
      }
    }

    loadInitialData();
    return () => { active = false; };
  }, [filtroSupermercado, filtroCategoria]);

  const ofertasOrdenadas = useMemo(() => {
    return [...ofertasReales].sort((a, b) => {
      const ahorroA = a.ahorro_real_pct ?? 0;
      const ahorroB = b.ahorro_real_pct ?? 0;
      return filtroOrden === "mayor" ? ahorroB - ahorroA : ahorroA - ahorroB;
    });
  }, [ofertasReales, filtroOrden]);

  async function handleToggleHistorial(idLink: string) {
    if (historialAbierto === idLink) {
      setHistorialAbierto(null);
      return;
    }
    setHistorialAbierto(idLink);
    setHistorialError(null);
    if (historiales[idLink]) return;

    setHistorialCargando(idLink);
    try {
      const puntos = await getHistorialProducto(idLink);
      setHistoriales((actuales) => ({ ...actuales, [idLink]: puntos }));
    } catch {
      setHistorialError("No se pudo cargar la serie temporal de este producto.");
    } finally {
      setHistorialCargando(null);
    }
  }

  async function handleSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!searchTerm.trim()) {
      setSearchError("Escribí al menos 2 letras para buscar.");
      setSearchResults([]);
      return;
    }

    setSearching(true);
    setSearchError(null);

    try {
      const results = await searchProductos(searchTerm.trim());
      setSearchResults(results);
      if (!results.length) {
        setSearchError("No se encontraron registros para ese criterio.");
      }
    } catch {
      setSearchResults([]);
      setSearchError("Error de comunicación con el motor de base de datos relacional.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      {isOffline && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2.5 text-center text-xs font-medium text-amber-800">
          Modo Local / Desconectado: No se pudo sincronizar con el nodo de base de datos.
        </div>
      )}

      <div className="mx-auto max-w-7xl px-6 py-10 sm:px-8 lg:px-10">
        {/* Header */}
        <header className="flex flex-col gap-6 border-b border-slate-200 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.35em] uppercase text-sky-700">FICHÁ</p>
            <p className="text-sm font-medium text-slate-600">Auditor de precios inteligente para Corrientes</p>
          </div>
          <nav className="flex flex-wrap items-center gap-6 text-sm font-medium text-slate-600">
            <a href="#inicio" className="transition hover:text-slate-900">Inicio</a>
            <a href="#buscador" className="transition hover:text-slate-900">Buscador</a>
            <a href="#ofertas-reales" className="transition hover:text-slate-900">Ofertas reales</a>
            <a href="#alertas-trampa" className="transition hover:text-slate-900">Alertas trampa</a>
          </nav>
        </header>

        {/* Sección Inicio */}
        <section id="inicio" className="mt-14 grid gap-14 lg:grid-cols-[1.4fr_0.8fr] lg:items-start">
          <div className="space-y-8">
            <div className="max-w-2xl space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 border border-sky-200">
                Auditoría Activa: 2.202 Enlaces Homologados
              </div>
              <h1 className="text-4xl font-semibold leading-tight tracking-tight text-slate-950 sm:text-5xl">
                Auditoría algorítmica para mitigar la asimetría de información en el retail local.
              </h1>
              <p className="text-base leading-7 text-slate-600">
                Extraemos registros diarios de Carrefour, Día, Depot y Delimart. Mediante una ventana móvil histórica de 21 días en PostgreSQL, clasificamos cada artículo en ofertas verificadas, aumentos inflacionarios o distorsiones comerciales.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Cadenas</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">4</p>
                <p className="mt-1 text-xs text-slate-500">Relevamiento regional continuo</p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Ventana Móvil</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">21 Días</p>
                <p className="mt-1 text-xs text-slate-500">Línea de base analítica SQL</p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Semáforo</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">3 Estados</p>
                <p className="mt-1 text-xs text-slate-500">Real, Neutral y Trampa</p>
              </div>
            </div>
          </div>

          <aside className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Rigor Metodológico</p>
            <div className="mt-6 space-y-4">
              <div className="rounded-2xl bg-slate-50 p-5 border border-slate-100">
                <p className="text-xs uppercase tracking-wider font-semibold text-slate-700">Ahorro de Cartel vs. Ahorro Real</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  Las promociones nominales suelen aplicarse sobre listas infladas. El motor matemático compara el precio efectivo contra la serie temporal histórica del producto para calcular el ahorro neto verificable.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-white p-4 border border-slate-200">
                  <p className="text-[0.65rem] uppercase tracking-wider text-slate-400">Tolerancia Inflado</p>
                  <p className="mt-1 text-base font-bold text-rose-600">+5.0%</p>
                </div>
                <div className="rounded-2xl bg-white p-4 border border-slate-200">
                  <p className="text-[0.65rem] uppercase tracking-wider text-slate-400">Umbral Ahorro</p>
                  <p className="mt-1 text-base font-bold text-emerald-600">&gt;3.0%</p>
                </div>
              </div>
            </div>
          </aside>
        </section>

        {/* Buscador de Precios */}
        <section id="buscador" className="mt-20">
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-sky-700">Explorador Analítico</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Búsqueda y Contraste de Series de Precios</h2>
            <p className="mt-1 text-sm text-slate-600">Búsqueda sobre el catálogo maestro parametrizada con operadores de coincidencia parcial.</p>
          </div>

          <form onSubmit={handleSearch} className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Buscar producto (ej: 'yerba', 'leche', 'aceite')"
              className="rounded-2xl border border-slate-200 bg-white px-5 py-3.5 text-sm text-slate-950 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
            <button
              type="submit"
              className="rounded-2xl bg-slate-950 px-8 py-3.5 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              {searching ? "Consultando..." : "Consultar"}
            </button>
          </form>

          <div className="mt-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            {searchError ? (
              <p className="text-sm text-rose-600">{searchError}</p>
            ) : searchResults.length ? (
              <div className="space-y-4">
                <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Registros Coincidentes</p>
                <div className="divide-y divide-slate-100">
                  {searchResults.slice(0, 8).map((producto) => (
                    <div key={producto.id_link} className="py-4 space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                        <div>
                          <span className="text-[0.65rem] font-bold uppercase tracking-wider text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-100 mr-2">
                            {producto.supermercado}
                          </span>
                          <span className="text-sm font-semibold text-slate-900">{producto.nombre_generico}</span>
                        </div>
                        <BadgeSemaforo semaforo={producto.semaforo} dias={producto.dias_con_datos} />
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 rounded-2xl p-3 text-xs">
                        <div>
                          <p className="text-[0.65rem] uppercase text-slate-400">Precio Lista</p>
                          <p className="font-semibold text-slate-700">{formatoPrecio(producto.precio_normal)}</p>
                        </div>
                        <div>
                          <p className="text-[0.65rem] uppercase text-slate-400">Precio Final Hoy</p>
                          <p className="font-bold text-slate-950">{formatoPrecio(precioFinal(producto))}</p>
                        </div>
                        <div>
                          <p className="text-[0.65rem] uppercase text-slate-400">Promedio Histórico (21d)</p>
                          <p className="font-semibold text-slate-700">{formatoPrecio(producto.promedio_normal_21d)}</p>
                        </div>
                        <div>
                          <p className="text-[0.65rem] uppercase text-slate-400">Ahorro Real Auditado</p>
                          <p className={`font-bold ${producto.ahorro_real_pct && producto.ahorro_real_pct > 0 ? "text-emerald-700" : "text-slate-600"}`}>
                            {producto.ahorro_real_pct != null ? `${producto.ahorro_real_pct.toFixed(1)}%` : "0.0%"}
                          </p>
                        </div>
                      </div>

                      <div className="text-[0.65rem] text-slate-400 font-mono">
                        Base: {producto.dias_con_datos ?? 0} días muestreados | Clasificación: {producto.clasificacion ?? "NEUTRAL"}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleToggleHistorial(producto.id_link)}
                        aria-expanded={historialAbierto === producto.id_link}
                        className="text-xs font-semibold text-sky-700 hover:text-sky-900"
                      >
                        {historialAbierto === producto.id_link ? "Ocultar evolución de precios" : "Ver evolución de precios (21 días)"}
                      </button>
                      {historialAbierto === producto.id_link && (
                        historialCargando === producto.id_link
                          ? <p className="mt-3 text-xs text-slate-500">Cargando historial...</p>
                          : historialError
                            ? <p className="mt-3 text-xs text-rose-600">{historialError}</p>
                            : (
                              <>
                                <GraficoHistorial puntos={historiales[producto.id_link] ?? []} />
                                {historiales[producto.id_link]?.length > 0 && (
                                  <button type="button" onClick={() => descargarHistorialCsv(producto, historiales[producto.id_link])} className="mt-2 text-xs font-semibold text-sky-700 hover:text-sky-900 print:hidden">
                                    Exportar esta serie a CSV
                                  </button>
                                )}
                              </>
                            )
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">Ingrese un término para auditar precios frente a la serie temporal histórica.</p>
            )}
          </div>
        </section>

        {/* Filtros compartidos por ofertas reales y alertas trampa */}
        <div className="mt-20 mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <label className="text-xs font-semibold text-slate-600">
            Supermercado
            <select value={filtroSupermercado} onChange={(event) => setFiltroSupermercado(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900">
              <option value="">Todos los supermercados</option>
              {opcionesFiltros.supermercados.map((supermercado) => <option key={supermercado} value={supermercado}>{supermercado}</option>)}
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-600">
            Categoría
            <select value={filtroCategoria} onChange={(event) => setFiltroCategoria(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900">
              <option value="">Todas las categorías</option>
              {opcionesFiltros.categorias.map((categoria) => <option key={categoria} value={categoria}>{categoria}</option>)}
            </select>
          </label>
        </div>

        {/* Sección: Ofertas Reales */}
        <section id="ofertas-reales" className="mt-20">
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-emerald-700">Capa Oro: Semáforo Verde</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Descuentos Reales Verificados</h2>
            <p className="mt-1 text-sm text-slate-600">Artículos cuyo precio final es estrictamente inferior al promedio histórico de 21 días (Ahorro Real &gt; 3%).</p>
            <div className="mt-4 flex flex-wrap gap-2 print:hidden">
              <button type="button" onClick={() => descargarCsv(ofertasReales, "ofertas-reales")} disabled={!ofertasReales.length} className="rounded-xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">Descargar CSV ({ofertasReales.length})</button>
              <button type="button" onClick={() => imprimirReporte("Ofertas reales verificadas", ofertasReales, { supermercado: filtroSupermercado, categoria: filtroCategoria })} disabled={!ofertasReales.length} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40">Imprimir / Guardar PDF</button>
            </div>
          </div>
          {/* Grilla de Destacados */}
          <div className="grid gap-6 xl:grid-cols-3">
            {ofertasReales.length === 0 ? (
              <p className="xl:col-span-3 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">No hay ofertas reales para los filtros seleccionados.</p>
            ) : ofertasReales.slice(0, 6).map((producto) => (
              <div key={producto.id_link} className="rounded-[2rem] border border-emerald-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[0.65rem] font-bold uppercase tracking-wider text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-100">
                      {producto.supermercado}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 border border-emerald-200">
                      🟢 -{producto.ahorro_real_pct != null ? producto.ahorro_real_pct.toFixed(1) : 0}% Real
                    </span>
                  </div>
                  <p className="mt-3 text-base font-semibold text-slate-950 line-clamp-2">{producto.nombre_generico}</p>
                </div>

                <div className="mt-6 space-y-3">
                  <div className="grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-xs">
                    <div>
                      <p className="text-[0.65rem] uppercase text-slate-400">Precio Hoy</p>
                      <p className="text-base font-bold text-slate-950">{formatoPrecio(precioFinal(producto))}</p>
                    </div>
                    <div>
                      <p className="text-[0.65rem] uppercase text-slate-400">Promedio 21d</p>
                      <p className="text-base font-semibold text-slate-600">{formatoPrecio(producto.promedio_normal_21d)}</p>
                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-50 p-2.5 flex items-center justify-between text-xs">
                    <span className="text-[0.7rem] text-slate-500">Cartel de Oferta:</span>
                    <span className="font-semibold text-slate-700">
                      {producto.ahorro_nominal_pct != null ? `${producto.ahorro_nominal_pct.toFixed(1)}% OFF` : "Sin Cartel"}
                    </span>
                  </div>

                  <p className="text-[0.65rem] text-slate-400 font-mono">
                    Muestra histórica: {producto.dias_con_datos ?? 0} días evaluados
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Tabla de Ranking Dinámico */}
          <div className="mt-10 rounded-[2rem] border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-5">
              <div>
                <h3 className="text-lg font-semibold text-slate-950">Explorador de Dispersión de Descuentos</h3>
                <p className="text-xs text-slate-500 mt-0.5">Ordenamiento reactivo por tasa de ahorro real calculada.</p>
              </div>

              <div className="inline-flex rounded-xl bg-slate-100 p-1 border border-slate-200">
                <button
                  type="button"
                  onClick={() => setFiltroOrden("mayor")}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    filtroOrden === "mayor" ? "bg-white text-slate-950 shadow-sm" : "text-slate-600 hover:text-slate-950"
                  }`}
                >
                  Mayor Ahorro Real
                </button>
                <button
                  type="button"
                  onClick={() => setFiltroOrden("menor")}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    filtroOrden === "menor" ? "bg-white text-slate-950 shadow-sm" : "text-slate-600 hover:text-slate-950"
                  }`}
                >
                  Menor Ahorro Real
                </button>
              </div>
            </div>

            <div className="mt-4 divide-y divide-slate-100">
              {ofertasOrdenadas.length === 0 ? (
                <p className="py-6 text-center text-xs text-slate-500">No hay registros analíticos disponibles en el entorno.</p>
              ) : (
                ofertasOrdenadas.slice(0, 10).map((prod) => (
                  <div key={prod.id_link} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold uppercase text-[0.65rem] text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-100">
                          {prod.supermercado}
                        </span>
                        <span className="font-semibold text-slate-900">{prod.nombre_generico}</span>
                      </div>
                      <p className="text-[0.7rem] text-slate-400 mt-1">
                        Base 21d: {formatoPrecio(prod.promedio_normal_21d)} | Lista: {formatoPrecio(prod.precio_normal)}
                      </p>
                    </div>

                    <div className="flex items-center gap-6 sm:justify-end">
                      <div className="text-right">
                        <p className="text-[0.65rem] text-slate-400 uppercase">Precio Pagable</p>
                        <p className="text-sm font-bold text-slate-950">{formatoPrecio(precioFinal(prod))}</p>
                      </div>
                      <div className="text-right min-w-[80px]">
                        <span className="inline-block rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1 font-bold">
                          -{prod.ahorro_real_pct != null ? prod.ahorro_real_pct.toFixed(1) : 0}% Real
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Sección: Alertas Trampa */}
        <section id="alertas-trampa" className="mt-20">
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-rose-600">Capa Oro: Semáforo Rojo</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Ofertas Trampa Detectadas</h2>
            <p className="mt-1 text-sm text-slate-600">
              Artículos cuyo precio de lista fue inflado más de un 5% respecto a su promedio histórico, simulando un descuento engañoso.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 print:hidden">
              <button type="button" onClick={() => descargarCsv(alertasTrampa, "alertas-trampa")} disabled={!alertasTrampa.length} className="rounded-xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">Descargar CSV ({alertasTrampa.length})</button>
              <button type="button" onClick={() => imprimirReporte("Alertas de precios", alertasTrampa, { supermercado: filtroSupermercado, categoria: filtroCategoria })} disabled={!alertasTrampa.length} className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40">Imprimir / Guardar PDF</button>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            {alertasTrampa.length === 0 ? (
              <p className="xl:col-span-3 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">No hay alertas trampa para los filtros seleccionados.</p>
            ) : alertasTrampa.slice(0, 6).map((producto) => (
              <div key={producto.id_link} className="rounded-[2rem] border border-rose-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[0.65rem] font-bold uppercase tracking-wider text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-100">
                      {producto.supermercado}
                    </span>
                    <span className="inline-flex items-center rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-bold text-rose-700 border border-rose-200">
                      🔴 Inflado Falso
                    </span>
                  </div>
                  <p className="mt-3 text-base font-semibold text-slate-950 line-clamp-2">{producto.nombre_generico}</p>
                </div>

                <div className="mt-6 space-y-3">
                  <div className="grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-xs">
                    <div>
                      <p className="text-[0.65rem] uppercase text-slate-400">Precio Lista Hoy</p>
                      <p className="text-base font-bold text-rose-600">{formatoPrecio(producto.precio_normal)}</p>
                    </div>
                    <div>
                      <p className="text-[0.65rem] uppercase text-slate-400">Promedio Real 21d</p>
                      <p className="text-base font-semibold text-slate-700">{formatoPrecio(producto.promedio_normal_21d)}</p>
                    </div>
                  </div>

                  <div className="rounded-xl bg-rose-50/50 p-2.5 flex items-center justify-between text-xs border border-rose-100">
                    <span className="text-[0.7rem] text-rose-600">Descuento Anunciado:</span>
                    <span className="font-semibold text-rose-700">
                      {producto.ahorro_nominal_pct != null ? `${producto.ahorro_nominal_pct.toFixed(1)}% OFF` : "Publicitado"}
                    </span>
                  </div>

                  <p className="text-[0.65rem] text-slate-400 font-mono">
                    Base: {producto.dias_con_datos ?? 0} días | Estado: Distorsión Comercial
                  </p>
                </div>
              </div>
            ))}
          </div>

          {!initialLoading && !initialError && alertasTrampa.length === 0 && (
            <p className="mt-6 text-sm text-slate-500">No hay alertas trampa clasificadas en la última captura.</p>
          )}
        </section>



        {/* Footer */}
        <footer className="mt-24 border-t border-slate-200 py-10">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-sky-700">FICHÁ</p>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">
                Auditoría comparativa de precios en supermercados de Corrientes. La clasificación se calcula a partir del precio actual y el histórico disponible de 21 días.
              </p>
            </div>
            <div className="text-sm text-slate-500 sm:text-right">
              <p>Datos recolectados desde fuentes comerciales públicas.</p>
              <p className="mt-1">Proyecto de tesis · 2026</p>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

function escaparCsv(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function escaparHtml(value: string | number | null | undefined): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character] ?? character);
}

function descargarCsv(productos: ProductoAuditado[], tipo: string) {
  const encabezados = ["Fecha de emisión", "Supermercado", "Categoría", "Producto", "Precio lista", "Precio descuento", "Precio efectivo", "Promedio histórico 21 días", "Ahorro real (%)", "Ahorro nominal (%)", "Semáforo", "Fecha de captura", "URL"];
  const emitido = new Date().toLocaleString("es-AR");
  const filas = productos.map((producto) => [
    emitido,
    producto.supermercado,
    producto.categoria,
    producto.nombre_generico,
    producto.precio_normal,
    producto.precio_descuento,
    precioFinal(producto),
    producto.promedio_normal_21d,
    producto.ahorro_real_pct,
    producto.ahorro_nominal_pct,
    producto.semaforo,
    producto.created_at,
    producto.url_producto,
  ]);
  const csv = [encabezados, ...filas].map((fila) => fila.map(escaparCsv).join(";")).join("\r\n");
  const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  const objectUrl = URL.createObjectURL(blob);
  link.href = objectUrl;
  link.download = `ficha-${tipo}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

function descargarHistorialCsv(producto: ProductoAuditado, puntos: PuntoHistorial[]) {
  const encabezados = ["Producto", "Supermercado", "Fecha", "Precio lista", "Precio descuento", "Precio efectivo"];
  const filas = puntos.map((punto) => [
    producto.nombre_generico,
    producto.supermercado,
    punto.fecha,
    punto.precio_normal,
    punto.precio_descuento,
    punto.precio_final,
  ]);
  const csv = [encabezados, ...filas].map((fila) => fila.map(escaparCsv).join(";")).join("\r\n");
  const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  const objectUrl = URL.createObjectURL(blob);
  link.href = objectUrl;
  link.download = `ficha-historial-${producto.id_link}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

function imprimirReporte(
  tipo: string,
  productos: ProductoAuditado[],
  filtros: { supermercado: string; categoria: string },
) {
  const ventana = window.open("", "_blank", "width=1000,height=750");
  if (!ventana) return;
  const filas = productos.map((producto) => `
    <tr>
      <td>${escaparHtml(producto.supermercado)}</td>
      <td>${escaparHtml(producto.categoria)}</td>
      <td>${escaparHtml(producto.nombre_generico)}</td>
      <td>${escaparHtml(formatoPrecio(precioFinal(producto)))}</td>
      <td>${escaparHtml(producto.promedio_normal_21d == null ? "-" : formatoPrecio(producto.promedio_normal_21d))}</td>
      <td>${escaparHtml(producto.ahorro_real_pct == null ? "-" : `${producto.ahorro_real_pct.toFixed(1)}%`)}</td>
      <td>${escaparHtml(producto.semaforo)}</td>
      <td>${escaparHtml(producto.created_at)}</td>
    </tr>`).join("");
  const tituloSeguro = escaparHtml(tipo);
  const supermercadoSeguro = escaparHtml(filtros.supermercado || "Todos");
  const categoriaSegura = escaparHtml(filtros.categoria || "Todas");
  ventana.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Reporte FICHÁ - ${tituloSeguro}</title>
    <style>
      body{font-family:Arial,sans-serif;color:#0f172a;margin:32px}header{border-bottom:2px solid #0284c7;padding-bottom:14px;margin-bottom:24px}h1{margin:0 0 8px;font-size:24px}p{color:#475569;font-size:12px}.summary{display:flex;gap:24px;margin:20px 0}.summary div{padding:12px;background:#f1f5f9;border-radius:8px}table{width:100%;border-collapse:collapse;font-size:10px}th,td{text-align:left;padding:8px;border-bottom:1px solid #cbd5e1}th{background:#e2e8f0}footer{margin-top:24px;font-size:10px;color:#64748b}@media print{body{margin:12mm}button{display:none}}
    </style></head><body>
    <header><strong>FICHÁ · Auditoría de precios</strong><h1>${tituloSeguro}</h1><p>Emitido: ${escaparHtml(new Date().toLocaleString("es-AR"))} · Registros: ${productos.length}</p><p>Reporte generado con los filtros activos en la plataforma. Los porcentajes corresponden a los campos calculados por el sistema.</p></header>
    <div class="summary"><div><strong>Productos:</strong> ${productos.length}</div><div><strong>Supermercado:</strong> ${supermercadoSeguro}</div><div><strong>Categoría:</strong> ${categoriaSegura}</div></div>
    <table><thead><tr><th>Cadena</th><th>Categoría</th><th>Producto</th><th>Precio efectivo</th><th>Promedio histórico</th><th>Ahorro real</th><th>Estado</th><th>Captura</th></tr></thead><tbody>${filas}</tbody></table>
    <footer>FICHÁ · Fuente: registros recolectados desde fuentes comerciales públicas. El reporte refleja la información disponible al momento de emisión.</footer>
    <script>window.onload=()=>window.print()</script></body></html>`);
  ventana.document.close();
}