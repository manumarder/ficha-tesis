"use client";

import { useEffect, useState, useMemo } from "react";
import { getAlertasTrampa, getOfertasReales, ProductoAuditado, searchProductos } from "./services/api";

function precioFinal(producto: ProductoAuditado) {
  return producto.precio_final ?? producto.precio_descuento ?? producto.precio_normal;
}

function formatoPrecio(value?: number) {
  return value != null ? `$${value.toFixed(2)}` : "-";
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

  // Estado para la nueva tabla interactiva de ordenamiento por descuento
  const [filtroOrden, setTipoOrden] = useState<"mayor" | "menor">("mayor");

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [reales, trampas] = await Promise.all([getOfertasReales(), getAlertasTrampa()]);
        setOfertasReales(reales);
        setAlertasTrampa(trampas);
      } catch {
        setInitialError("No se pudo cargar la auditoría. Verificá que la API esté activa e intentá recargar.");
      } finally {
        setInitialLoading(false);
      }
    }

    loadInitialData();
  }, []);

  // Lista ordenada dinámicamente según el filtro seleccionado
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
        setSearchError("No se encontraron productos para esa búsqueda.");
      }
    } catch {
      setSearchResults([]);
      setSearchError("Hubo un problema buscando productos. Probá de nuevo.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
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
              <p className="text-sm uppercase tracking-[0.35em] text-sky-700">Auditoría de precios en Corrientes</p>
              <h1 className="text-5xl font-semibold leading-tight tracking-tight text-slate-950 sm:text-6xl">
                FICHÁ ayuda a los correntinos a encontrar ofertas reales y detectar trampas de precio.
              </h1>
              <p className="text-lg leading-8 text-slate-600">
                Extraemos precios de cuatro supermercados en Corrientes, mantenemos un histórico de 21 días y clasificamos cada producto como oferta real, normal o oferta trampa.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl border border-slate-200 bg-white px-6 py-7 shadow-sm">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Supermercados</p>
                <p className="mt-4 text-3xl font-semibold text-slate-950">4</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">Cadena completa de Corrientes.</p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-white px-6 py-7 shadow-sm">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Auditoría</p>
                <p className="mt-4 text-3xl font-semibold text-slate-950">21 días</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">Promedios móviles para detectar ofertas.</p>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-white px-6 py-7 shadow-sm">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Clasificación</p>
                <p className="mt-4 text-3xl font-semibold text-slate-950">3 grupos</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">Ofertas reales, normales y trampa.</p>
              </div>
            </div>
          </div>

          <aside className="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-lg shadow-slate-200/50">
            <p className="text-xs uppercase tracking-[0.35em] text-slate-500">Primer vistazo</p>
            <div className="mt-8 space-y-6">
              <div className="rounded-3xl bg-slate-50 p-6">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Dónde conviene</p>
                <h2 className="mt-4 text-2xl font-semibold text-slate-950">Decide rápido con datos claros</h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">Compara precios por supermercado y conoce si la oferta es real o es una trampa.</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl bg-white p-5 border border-slate-200">
                  <p className="text-[0.625rem] uppercase tracking-[0.3em] text-slate-500">Beneficio</p>
                  <p className="mt-3 text-lg font-semibold text-slate-950">Transparencia</p>
                </div>
                <div className="rounded-3xl bg-white p-5 border border-slate-200">
                  <p className="text-[0.625rem] uppercase tracking-[0.3em] text-slate-500">Alcance</p>
                  <p className="mt-3 text-lg font-semibold text-slate-950">Fuentes reales</p>
                </div>
              </div>
            </div>
          </aside>
        </section>

        {/* Buscador */}
        <section id="buscador" className="mt-24">
          <div className="mb-10 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.35em] text-sky-700">Buscador</p>
              <h2 className="mt-4 text-3xl font-semibold text-slate-950">Busca productos y compará precios</h2>
              <p className="mt-3 text-base leading-7 text-slate-600">Ingresá un término como “yerba” o “pan” y obtené los resultados de todos los supermercados.</p>
            </div>
          </div>

          <form onSubmit={handleSearch} className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Buscar producto, marca o categoría"
              className="rounded-3xl border border-slate-200 bg-white px-6 py-4 text-slate-950 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
            />
            <button
              type="submit"
              className="rounded-3xl bg-slate-950 px-8 py-4 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              {searching ? "Buscando..." : "Buscar"}
            </button>
          </form>

          <div className="mt-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            {searchError ? (
              <p className="text-sm text-rose-600">{searchError}</p>
            ) : searchResults.length ? (
              <div className="space-y-6">
                <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Resultados</p>
                <div className="space-y-4">
                  {searchResults.slice(0, 7).map((producto) => (
                    <div key={producto.id_link} className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-semibold text-slate-950">{producto.nombre_generico}</p>
                          <p className="mt-1 text-sm text-slate-600">{producto.supermercado}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-semibold text-slate-950">{formatoPrecio(precioFinal(producto))}</p>
                          <p className="text-sm text-slate-500">{producto.semaforo ?? "Normal"}</p>
                        </div>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div>
                          <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Precio normal</p>
                          <p className="mt-2 text-sm text-slate-700">{formatoPrecio(producto.precio_normal)}</p>
                        </div>
                        <div>
                          <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Precio descuento</p>
                          <p className="mt-2 text-sm text-slate-700">{formatoPrecio(producto.precio_descuento)}</p>
                        </div>
                        <div>
                          <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Ahorro</p>
                          <p className="mt-2 text-sm text-slate-700">{producto.ahorro_real_pct != null ? `${producto.ahorro_real_pct.toFixed(1)}%` : "-"}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-600">Probá buscando un producto para ver las mejores ofertas y comparaciones.</p>
            )}
          </div>
        </section>

        {/* Sección: Ofertas Reales con Tarjetas + Nueva Tabla de Filtro */}
        <section id="ofertas-reales" className="mt-24">
          <div className="mb-10">
            <p className="text-sm uppercase tracking-[0.35em] text-sky-700">Ofertas reales</p>
            <h2 className="mt-4 text-3xl font-semibold text-slate-950">Las mejores oportunidades</h2>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Los productos marcados con semáforo verde cuya rebaja fue validada contra su promedio histórico de 21 días.
            </p>
          </div>

          {/* Grilla Superior de Destacados */}
          <div className="grid gap-6 xl:grid-cols-3">
            {ofertasReales.slice(0, 6).map((producto) => (
              <div key={producto.id_link} className="relative rounded-[2rem] border border-emerald-200 bg-white p-6 shadow-sm transition hover:shadow-md">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-700">{producto.supermercado}</p>
                  <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200">
                    🟢 {producto.ahorro_real_pct != null ? `${producto.ahorro_real_pct.toFixed(1)}% Ahorro` : "Oferta"}
                  </span>
                </div>
                <p className="mt-4 text-xl font-semibold text-slate-950">{producto.nombre_generico}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Precio final</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">{formatoPrecio(precioFinal(producto))}</p>
                  </div>
                  <div>
                    <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Ahorro real</p>
                    <p className="mt-2 text-lg font-semibold text-emerald-600">
                      {producto.ahorro_real_pct != null ? `${producto.ahorro_real_pct.toFixed(1)}%` : "-"}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* NUEVO COMPONENTE: Tabla de Ranking con Botones de Filtro */}
          <div className="mt-12 rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-6">
              <div>
                <h3 className="text-xl font-semibold text-slate-950">Explorador General de Descuentos Genuinos</h3>
                <p className="text-sm text-slate-600 mt-1">
                  Ordená el catálogo completo de productos auditados según su margen de ahorro real.
                </p>
              </div>

              {/* Botones de Control / Toggle */}
              <div className="inline-flex rounded-2xl bg-slate-100 p-1.5 border border-slate-200">
                <button
                  type="button"
                  onClick={() => setTipoOrden("mayor")}
                  className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
                    filtroOrden === "mayor"
                      ? "bg-white text-slate-950 shadow-sm"
                      : "text-slate-600 hover:text-slate-950"
                  }`}
                >
                  🟢 Mayores Descuentos
                </button>
                <button
                  type="button"
                  onClick={() => setTipoOrden("menor")}
                  className={`rounded-xl px-4 py-2 text-xs font-semibold transition ${
                    filtroOrden === "menor"
                      ? "bg-white text-slate-950 shadow-sm"
                      : "text-slate-600 hover:text-slate-950"
                  }`}
                >
                  📉 Menores Descuentos
                </button>
              </div>
            </div>

            {/* Listado / Tabla Responsiva */}
            <div className="mt-6 divide-y divide-slate-100">
              {initialLoading ? (
                <p className="py-6 text-center text-sm text-slate-500">Cargando catálogo auditado...</p>
              ) : initialError ? (
                <p className="py-6 text-center text-sm text-rose-600">{initialError}</p>
              ) : ofertasOrdenadas.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-500">Todavía no hay ofertas reales clasificadas en la última captura.</p>
              ) : (
                ofertasOrdenadas.slice(0, 10).map((prod) => (
                  <div key={prod.id_link} className="flex flex-col sm:flex-row sm:items-center justify-between py-4 gap-4 hover:bg-slate-50/80 px-4 rounded-2xl transition">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-semibold uppercase tracking-wider text-sky-700 bg-sky-50 px-2 py-0.5 rounded-md border border-sky-100">
                          {prod.supermercado}
                        </span>
                        <p className="text-base font-semibold text-slate-900">{prod.nombre_generico}</p>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        Precio Lista: {formatoPrecio(prod.precio_normal)}
                      </p>
                    </div>

                    <div className="flex items-center gap-6 sm:justify-end">
                      <div className="text-right">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">Precio Final</p>
                        <p className="text-base font-bold text-slate-950">{formatoPrecio(precioFinal(prod))}</p>
                      </div>

                      <div className="text-right min-w-[90px]">
                        <span className={`inline-block rounded-xl px-3 py-1.5 text-xs font-bold ${
                          (prod.ahorro_real_pct ?? 0) >= 20 
                            ? "bg-emerald-100 text-emerald-800" 
                            : "bg-emerald-50 text-emerald-700"
                        }`}>
                          -{prod.ahorro_real_pct != null ? prod.ahorro_real_pct.toFixed(1) : "0"}%
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* Alertas Trampa */}
        <section id="alertas-trampa" className="mt-24">
          <div className="mb-10">
            <p className="text-sm uppercase tracking-[0.35em] text-rose-600">Alertas trampa</p>
            <h2 className="mt-4 text-3xl font-semibold text-slate-950">Productos que conviene evitar</h2>
            <p className="mt-3 text-base leading-7 text-slate-600">Listamos los productos con semáforo rojo y precio inflado en comparación a su historial.</p>
          </div>
          <div className="grid gap-6 xl:grid-cols-3">
            {alertasTrampa.slice(0, 6).map((producto) => (
              <div key={producto.id_link} className="rounded-[2rem] border border-rose-200 bg-white p-6 shadow-sm transition hover:shadow-md">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-rose-600">{producto.supermercado}</p>
                  <span className="inline-flex items-center rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 border border-rose-200">
                    🔴 Inflado Falso
                  </span>
                </div>
                <p className="mt-4 text-xl font-semibold text-slate-950">{producto.nombre_generico}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Precio final</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">{formatoPrecio(precioFinal(producto))}</p>
                  </div>
                  <div>
                    <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Semáforo</p>
                    <p className="mt-2 text-lg font-semibold text-rose-600">{producto.semaforo ?? "🔴"}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {!initialLoading && !initialError && alertasTrampa.length === 0 && (
            <p className="mt-6 text-sm text-slate-500">No hay alertas trampa clasificadas en la última captura.</p>
          )}
        </section>

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