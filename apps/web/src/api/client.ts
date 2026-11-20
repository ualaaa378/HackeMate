// Única puerta de la app hacia el backend. Las pantallas solo importan de aquí.
// Con VITE_USE_MOCKS=true (o sin VITE_API_URL) responde con src/mocks/eventos.json,
// copia de contracts/fixtures/eventos.json.
// Con la API configurada, si no responde o el endpoint aún no existe, se vuelve a los mocks
// para que la demo no se caiga. Los errores de negocio de la API sí llegan a la pantalla.

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

// Fallo que no viene de la lógica de la API: sin red, CORS, 5xx o ruta sin implementar.
class ApiNoDisponible extends Error {}

let usandoRespaldo = false;
/** true si alguna llamada a la API real ha fallado y se han servido mocks. */
export function enModoRespaldo(): boolean {
  return USAR_MOCKS || usandoRespaldo;
}

async function peticion<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const cabeceras: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) cabeceras.Authorization = `Bearer ${token}`;
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}/api/v1${ruta}`, { ...opciones, headers: { ...cabeceras, ...opciones.headers } });
  } catch {
    throw new ApiNoDisponible('sin conexion con la API');
  }
  if (!resp.ok) {
    const cuerpo = (await resp.json().catch(() => null)) as Partial<ApiError> | null;
    if (!cuerpo?.error || resp.status >= 500) throw new ApiNoDisponible(`${resp.status} ${resp.statusText}`);
    throw new ErrorApi(cuerpo.error.code, cuerpo.error.message, resp.status);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

async function conRespaldo<T>(real: () => Promise<T>, mock: () => Promise<T>): Promise<T> {
  if (USAR_MOCKS) return mock();
  try {
    const r = await real();
    usandoRespaldo = false;
    return r;
  } catch (e) {
    if (!(e instanceof ApiNoDisponible)) throw e;
    console.warn('[api] usando mocks:', e.message);
    usandoRespaldo = true;
    return mock();
  }
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
const USUARIO_MOCK_ID = '00000000-0000-4000-8000-000000000001';
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
  return conRespaldo(
    () => peticion(`/eventos${query({ size: 100, ...filtros })}`),
    () => esperar(filtrarMock(filtros)),
  );
}

export function getEvento(id: string): Promise<Evento> {
  return conRespaldo(
    () => peticion(`/eventos/${id}`),
    () => {
      const e = mockEventos.find((x) => x.id === id);
      return e ? esperar(e) : Promise.reject(new ErrorApi('evento_no_encontrado', 'No existe ese evento', 404));
    },
  );
}

export function inscribirse(eventoId: string): Promise<Inscripcion> {
  return conRespaldo(
    () => peticion(`/eventos/${eventoId}/inscripciones`, { method: 'POST' }),
    () => {
      const e = mockEventos.find((x) => x.id === eventoId);
      const hayPlaza = e?.plazas_libres == null || e.plazas_libres > 0;
      if (e && e.plazas_libres != null && e.plazas_libres > 0) e.plazas_libres -= 1;
      if (e && hayPlaza) e.inscritos = (e.inscritos ?? 0) + 1;
      return esperar<Inscripcion>({
        id: crypto.randomUUID(),
        evento_id: eventoId,
        usuario_id: USUARIO_MOCK_ID,
        estado: hayPlaza ? 'confirmada' : 'lista_espera',
        plazas: 1,
        canal: 'web',
      });
    },
  );
}

export function urlIcs(eventoId: string): string {
  if (enModoRespaldo()) return '#';
  return `${API_URL}/api/v1/eventos/${eventoId}/ics`;
}

export const MUNICIPIOS = ['Lucainena de las Torres', 'Senés', 'Velefique', 'Uleila del Campo', 'Tahal'];
