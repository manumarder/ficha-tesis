const BASE_URL = 'http://127.0.0.1:8000';

export interface ProductoAuditado {
  id_link: string;
  url_producto: string;
  nombre_generico: string;
  supermercado: string;
  created_at: string;
  precio_normal: number;
  precio_descuento: number;
  promedio_normal_21d: number;
  dias_con_datos: number;
  clasificacion: string;
  semaforo: string;
  ahorro_real_pct: number;
  ahorro_nominal_pct: number;
}

export async function getOfertasReales(): Promise<ProductoAuditado[]> {
  try {
    const res = await fetch(`${BASE_URL}/api/ofertas-reales`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Error al traer ofertas reales');
    const json = await res.json();
    return json.data || [];
  } catch (error) {
    console.error(error);
    return [];
  }
}

export async function getAlertasTrampa(): Promise<ProductoAuditado[]> {
  try {
    const res = await fetch(`${BASE_URL}/api/alertas-trampa`, { cache: 'no-store' });
    if (!res.ok) throw new Error('Error al traer alertas trampa');
    const json = await res.json();
    return json.data || [];
  } catch (error) {
    console.error(error);
    return [];
  }
}