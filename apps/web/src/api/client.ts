// Única puerta de la app hacia el backend. Las pantallas solo importan de aquí.
// Con VITE_USE_MOCKS=true (o sin VITE_API_URL) responde con src/mocks/eventos.json,
// copia de contracts/fixtures/eventos.json.

import eventosMock from '../mocks/eventos.json';
import type { ApiError, Evento, FiltrosEventos, Inscripcion, Pagina } from './types';

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';
export const USAR_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true' || !API_URL;

let token: string | null = null;
export function setToken(nuevo: string | null) {
  token = nuevo;
}

export class ErrorApi extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function peticion<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const cabeceras: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${API_URL}/api/v1${ruta}`, { ...opciones, headers: { ...cabeceras, ...opciones.headers } });
  if (!resp.ok) {
    const cuerpo = (await resp.json().catch(() => null)) as ApiError | null;
    throw new ErrorApi(cuerpo?.error.code ?? 'error_red', cuerpo?.error.message ?? resp.statusText, resp.status);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

function query(filtros: object): string {
  const p = new URLSearchParams();
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : '';
}

export function distanciaKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = (g: number) => (g * Math.PI) / 180;
  const a =
    Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ---------- mocks ----------
const mockEventos = eventosMock as Evento[];
const esperar = <T>(valor: T, ms = 250) => new Promise<T>((r) => setTimeout(() => r(valor), ms));

function filtrarMock(f: FiltrosEventos): Pagina<Evento> {
  let items = mockEventos.filter((e) => e.estado === 'publicado');
  if (f.municipio) items = items.filter((e) => e.municipio === f.municipio);
  if (f.categoria) items = items.filter((e) => e.categoria === f.categoria);
  if (f.desde) items = items.filter((e) => e.fecha_inicio >= f.desde!);
  if (f.hasta) items = items.filter((e) => e.fecha_inicio <= f.hasta!);
  if (f.lat != null && f.lon != null && f.radio_km)
    items = items.filter((e) => distanciaKm(f.lat!, f.lon!, e.lat, e.lon) <= f.radio_km!);
  items.sort((a, b) => a.fecha_inicio.localeCompare(b.fecha_inicio));
  const page = f.page ?? 1;
  const size = f.size ?? 50;
  return { items: items.slice((page - 1) * size, page * size), total: items.length, page, size };
}

// ---------- API pública ----------
export function getEventos(filtros: FiltrosEventos = {}): Promise<Pagina<Evento>> {
  if (USAR_MOCKS) return esperar(filtrarMock(filtros));
  return peticion(`/eventos${query(filtros)}`);
}

export function getEvento(id: string): Promise<Evento> {
  if (USAR_MOCKS) {
    const e = mockEventos.find((x) => x.id === id);
    return e ? esperar(e) : Promise.reject(new ErrorApi('evento_no_encontrado', 'No existe ese evento', 404));
  }
  return peticion(`/eventos/${id}`);
}

export function inscribirse(eventoId: string): Promise<Inscripcion> {
  if (USAR_MOCKS) {
    const e = mockEventos.find((x) => x.id === eventoId);
    const hayPlaza = e?.plazas_libres == null || e.plazas_libres > 0;
    if (e && e.plazas_libres != null && e.plazas_libres > 0) e.plazas_libres -= 1;
    if (e && hayPlaza) e.inscritos = (e.inscritos ?? 0) + 1;
    return esperar({ id: crypto.randomUUID(), evento_id: eventoId, estado: hayPlaza ? 'confirmada' : 'lista_espera' });
  }
  return peticion(`/eventos/${eventoId}/inscripciones`, { method: 'POST' });
}

export function urlIcs(eventoId: string): string {
  if (USAR_MOCKS) return '#';
  return `${API_URL}/api/v1/eventos/${eventoId}/ics`;
}

export const MUNICIPIOS = ['Lucainena de las Torres', 'Senés', 'Velefique', 'Uleila del Campo', 'Tahal'];
