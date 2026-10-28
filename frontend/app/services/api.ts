const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');

export interface ProductoAuditado {
  id_link: string;
  url_producto: string;
  nombre_generico: string;
  supermercado: string;
  created_at: string;
  precio_normal: number;
  precio_descuento?: number;
  precio_final?: number;
  promedio_normal_21d?: number;
  dias_con_datos?: number;
  clasificacion?: string;
  semaforo?: string;
  ahorro_real_pct?: number;
  ahorro_nominal_pct?: number;
  categoria?: string;
}

export interface OpcionesFiltros {
  supermercados: string[];
  categorias: string[];
}

export interface PuntoHistorial {
  fecha: string;
  precio_normal: number;
  precio_descuento?: number | null;
  precio_final: number;
}

export interface ResumenAuditoriaDiaria {
  id?: number;
  fecha_censo: string;
  total_catalogo: number;
  total_en_promo: number;
  promedio_descuento_cartel_pct: number;
  cant_ofertas_reales: number;
  pct_ofertas_reales: number;
  cant_ofertas_trampa: number;
  pct_ofertas_trampa: number;
  cant_neutrales: number;
  pct_neutrales: number;
  cant_sin_datos: number;
  pct_sin_datos: number;
  ahorro_real_promedio_pct: number;
}

export interface DesgloseSupermercado {
  supermercado: string;
  total_auditados: number;
  total_en_promo: number;
  promo_cartel_promedio_pct: number;
  cant_ofertas_reales: number;
  cant_ofertas_trampa: number;
  cant_neutrales: number;
  cant_sin_datos: number;
}

export interface DictamenGlobalResponse {
  status: string;
  fecha_emision: string;
  resumen_global: ResumenAuditoriaDiaria;
  desglose_supermercados: DesgloseSupermercado[];
}

function queryFiltros(filtros: { supermercado: string; categoria: string }): string {
  const params = new URLSearchParams();
  if (filtros.supermercado) params.set('supermercado', filtros.supermercado);
  if (filtros.categoria) params.set('categoria', filtros.categoria);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export async function getOpcionesFiltros(): Promise<OpcionesFiltros> {
  const res = await fetch(`${BASE_URL}/api/filtros`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Error al traer opciones de filtros');
  return res.json();
}

export async function getOfertasReales(filtros = { supermercado: '', categoria: '' }): Promise<ProductoAuditado[]> {
  const res = await fetch(`${BASE_URL}/api/ofertas-reales${queryFiltros(filtros)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Error al traer ofertas reales');
  const json = await res.json();
  return json.data || [];
}

export async function searchProductos(query: string): Promise<ProductoAuditado[]> {
  try {
    const res = await fetch(`${BASE_URL}/api/buscar?q=${encodeURIComponent(query)}`, { cache: 'no-store' });
    if (!res.ok) {
      const json = await res.json();
      throw new Error(json.detail || 'Error al buscar productos');
    }
    const json = await res.json();
    return json.data || [];
  } catch (error) {
    console.error(error);
    throw error;
  }
}

export async function getAlertasTrampa(filtros = { supermercado: '', categoria: '' }): Promise<ProductoAuditado[]> {
  const res = await fetch(`${BASE_URL}/api/alertas-trampa${queryFiltros(filtros)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Error al traer alertas trampa');
  const json = await res.json();
  return json.data || [];
}

export async function getHistorialProducto(idLink: string): Promise<PuntoHistorial[]> {
  const res = await fetch(`${BASE_URL}/api/productos/${encodeURIComponent(idLink)}/historial?dias=21`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Error al traer el historial del producto');
  const json = await res.json();
  return json.data || [];
}

export async function getResumenAuditoria(): Promise<ResumenAuditoriaDiaria | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/auditoria/resumen`, { cache: 'no-store' });
    if (!res.ok) return null;
    const json = await res.json();
    return json.data ?? null;
  } catch {
    return null;
  }
}

export async function getDictamenGlobal(): Promise<DictamenGlobalResponse | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/auditoria/dictamen-global`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}