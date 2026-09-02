"use client";

import { useEffect, useState, useMemo } from "react";
import { getAlertasTrampa, getOfertasReales, ProductoAuditado, searchProductos } from "./services/api";

function precioFinal(producto: ProductoAuditado): number {
  return producto.precio_descuento ?? producto.precio_normal;
}

function formatoPrecio(value?: number): string {
  return value != null ? `$${value.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "-";
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

export default function Home() {
  const [ofertasReales, setOfertasReales] = useState<ProductoAuditado[]>([]);
  const [alertasTrampa, setAlertasTrampa] = useState<ProductoAuditado[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<ProductoAuditado[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [filtroOrden, setFiltroOrden] = useState<"mayor" | "menor">("mayor");
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [reales, trampas] = await Promise.all([getOfertasReales(), getAlertasTrampa()]);
        setOfertasReales(reales);
        setAlertasTrampa(trampas);
        if (reales.length === 0 && trampas.length === 0) {
          setIsOffline(true);
        } else {
          setIsOffline(false);
        }
      } catch {
        setIsOffline(true);
      }
    }

    loadInitialData();
  }, []);

  const ofertasOrdenadas = useMemo(() => {
    return [...ofertasReales].sort((a, b) => {
      const ahorroA = a.ahorro_real_pct ?? 0;
      const ahorroB = b.ahorro_real_pct ?? 0;
      return filtroOrden === "mayor" ? ahorroB - ahorroA : ahorroA - ahorroB;
    });
  }, [ofertasReales, filtroOrden]);

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
          Modo Local / Desconectado: No se pudo sincronizar con el nodo de Supabase Cloud. Verifique la conexión a la base de datos.
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
            <a href="#chat" className="transition hover:text-slate-900">Módulo I+D</a>
          </nav>
        </header>

        {/* Hero Section */}
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
            <p className="mt-1 text-sm text-slate-600">Búsqueda sobre el catálogo maestro parametrizada con operadores de coincidencia parcial (ILIKE).</p>
          </div>

          <form onSubmit={handleSearch} className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Buscar producto (ej: 'yerba', 'pan flauta', 'leche')"
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
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">Ingrese un término para auditar precios frente a la serie temporal histórica.</p>
            )}
          </div>
        </section>

        {/* Sección: Oportunidades Reales */}
        <section id="ofertas-reales" className="mt-20">
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-emerald-700">Capa Oro: Semáforo Verde</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-950">Descuentos Reales Verificados</h2>
            <p className="mt-1 text-sm text-slate-600">Artículos cuyo precio final es estrictamente inferior al promedio histórico de 21 días (Ahorro Real &gt; 3%).</p>
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            {ofertasReales.slice(0, 6).map((producto) => (
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
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            {alertasTrampa.slice(0, 6).map((producto) => (
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
        </section>

        {/* Sección: Módulo de Interacción I+D */}
        <section id="chat" className="mt-20 rounded-[2rem] border border-slate-200 bg-slate-100 p-8 sm:p-10 shadow-sm">
          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Módulo Prospectivo (I+D)</p>
              <h2 className="mt-2 text-2xl font-semibold text-slate-950">Agente Conversacional sobre Protocolo MCP</h2>
              <p className="mt-3 text-sm leading-6 text-slate-600">
                Línea de investigación para desacoplar el razonamiento del modelo de lenguaje de la infraestructura de base de datos. Mediante herramientas del servidor FastMCP, el asistente consume de forma estricta las vistas de auditoría sin margen de alucinación.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-xs uppercase tracking-wider font-semibold text-slate-400">Consultas de Dominio Cerrado</p>
              <div className="mt-4 space-y-2 text-xs font-mono text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-100">
                <p>&gt; buscar_precios_producto(&quot;yerba&quot;)</p>
                <p>&gt; obtener_vista_auditoria(limit=50)</p>
                <p>&gt; optimizar_canasta(items=[...])</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}