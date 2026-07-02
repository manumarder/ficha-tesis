"use client";

import { useEffect, useState } from "react";
import { getAlertasTrampa, getOfertasReales, ProductoAuditado, searchProductos } from "./services/api";

function precioFinal(producto: ProductoAuditado) {
  return producto.precio_descuento ?? producto.precio_normal;
}

function formatoPrecio(value?: number) {
  return value != null ? `$${value.toFixed(2)}` : "-";
}

export default function Home() {
  const [ofertasReales, setOfertasReales] = useState<ProductoAuditado[]>([]);
  const [alertasTrampa, setAlertasTrampa] = useState<ProductoAuditado[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<ProductoAuditado[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    async function loadInitialData() {
      const [reales, trampas] = await Promise.all([getOfertasReales(), getAlertasTrampa()]);
      setOfertasReales(reales);
      setAlertasTrampa(trampas);
    }

    loadInitialData();
  }, []);

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
    } catch (error) {
      setSearchResults([]);
      setSearchError("Hubo un problema buscando productos. Probá de nuevo.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto max-w-7xl px-6 py-10 sm:px-8 lg:px-10">
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
            <a href="#chat" className="transition hover:text-slate-900">Chat</a>
          </nav>
        </header>

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

        <section id="ofertas-reales" className="mt-24">
          <div className="mb-10">
            <p className="text-sm uppercase tracking-[0.35em] text-sky-700">Ofertas reales</p>
            <h2 className="mt-4 text-3xl font-semibold text-slate-950">Las mejores oportunidades</h2>
            <p className="mt-3 text-base leading-7 text-slate-600">Los productos marcados como fuerza verde ordenados por ahorro real descendente.</p>
          </div>
          <div className="grid gap-6 xl:grid-cols-3">
            {ofertasReales.slice(0, 6).map((producto) => (
              <div key={producto.id_link} className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.28em] text-sky-700">{producto.supermercado}</p>
                <p className="mt-4 text-xl font-semibold text-slate-950">{producto.nombre_generico}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Precio final</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">{formatoPrecio(precioFinal(producto))}</p>
                  </div>
                  <div>
                    <p className="text-[0.675rem] uppercase tracking-[0.28em] text-slate-500">Ahorro</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">{producto.ahorro_real_pct != null ? `${producto.ahorro_real_pct.toFixed(1)}%` : "-"}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section id="alertas-trampa" className="mt-24">
          <div className="mb-10">
            <p className="text-sm uppercase tracking-[0.35em] text-sky-700">Alertas trampa</p>
            <h2 className="mt-4 text-3xl font-semibold text-slate-950">Productos que conviene evitar</h2>
            <p className="mt-3 text-base leading-7 text-slate-600">Listamos los productos con semáforo rojo y precio inflado en comparación a su historial.</p>
          </div>
          <div className="grid gap-6 xl:grid-cols-3">
            {alertasTrampa.slice(0, 6).map((producto) => (
              <div key={producto.id_link} className="rounded-[2rem] border border-rose-200 bg-white p-6 shadow-sm">
                <p className="text-xs uppercase tracking-[0.28em] text-rose-600">{producto.supermercado}</p>
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
        </section>

        <section id="chat" className="mt-24 rounded-[2rem] border border-slate-200 bg-slate-100 p-10 shadow-sm">
          <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
            <div>
              <p className="text-sm uppercase tracking-[0.35em] text-slate-500">Chat</p>
              <h2 className="mt-4 text-3xl font-semibold text-slate-950">Próximo paso: agente conversacional</h2>
              <p className="mt-4 text-base leading-7 text-slate-600">En la siguiente versión incorporamos un asistente que responde usando tu base de datos de precios y auditorías.</p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-8">
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Futura interfaz</p>
              <p className="mt-4 text-lg font-semibold text-slate-950">Consulta tu auditoría por chat</p>
              <div className="mt-6 rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                <p className="text-slate-900">Aquí podrás escribir preguntas como:</p>
                <ul className="mt-3 space-y-2 list-disc pl-5 text-slate-600">
                  <li>¿Cuál es la mejor oferta de yerba?</li>
                  <li>Mostrame productos con semáforo rojo.</li>
                  <li>¿Qué supermercado tiene la canasta más barata?</li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
