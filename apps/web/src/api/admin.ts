// Llamadas de la interfaz del ayuntamiento (moderador y publicador).
// Las rutas están en contracts/openapi.yaml, pero A aún no las tiene con JWT:
// POST/PATCH /eventos solo aceptan X-Internal-Token y la moderación no está implementada.
// Por eso, mientras no haya una sesión real de moderador o publicador, todo va con mocks (modo demo).

import { COORDENADAS, estadisticasMock, nuevoEventoMock, pendientesMock, publicadoresMock } from '../mocks/admin';

import { conRespaldo, esperar, mockEventos, peticion, propuestasMock, query } from './client';
import type {
  Decision,
  EstadoEvento,
  Estadisticas,
  Evento,
  EventoCrear,
  EventoEditar,
  Pagina,
  PendienteBandeja,
  Publicador,
} from './types';

let demo = true;
/** La pone el proveedor de acceso: true si se entra con el selector de rol de la demo. */
export function setAdminDemo(valor: boolean): void {
  demo = valor;
}

function llamar<T>(real: () => Promise<T>, mock: () => Promise<T>): Promise<T> {
  return demo ? mock() : conRespaldo(real, mock);
}

function pagina<T>(items: T[]): Pagina<T> {
  return { items, total: items.length, page: 1, size: Math.max(items.length, 1) };
}

// Eventos que no están publicados (rechazados, en revisión…) y por eso no viven en la agenda de mocks.
const eventosInternos: Evento[] = [];

function todosLosEventos(): Evento[] {
  const vistos = new Set<string>();
  return [...mockEventos, ...eventosInternos, ...pendientesMock.flatMap((p) => (p.evento ? [p.evento] : []))].filter(
    (e) => !vistos.has(e.id) && vistos.add(e.id),
  );
}

function pasarAPublicado(e: Evento) {
  e.estado = 'publicado';
  if (!mockEventos.some((x) => x.id === e.id)) mockEventos.push(e);
  const i = eventosInternos.findIndex((x) => x.id === e.id);
  if (i >= 0) eventosInternos.splice(i, 1);
}

// Las propuestas que se envían desde /proponer en modo demo entran en la bandeja.
function incorporarPropuestas() {
  for (const p of propuestasMock) {
    if (pendientesMock.some((x) => x.evento?.id === p.evento.id)) continue;
    const coords = COORDENADAS[p.evento.municipio];
    if (coords && !p.evento.lat) Object.assign(p.evento, coords);
    pendientesMock.unshift({
      tipo: 'evento',
      motivo: 'Plan propuesto por un vecino desde la app. Las propuestas vecinales siempre pasan por el ayuntamiento.',
      score_spam: null,
      evento: p.evento,
      propuesta: p.ayuntamiento,
    });
  }
}

// ---------- bandeja ----------
export function getPendientes(): Promise<Pagina<PendienteBandeja>> {
  return llamar(
    () => peticion('/moderacion/pendientes?size=100'),
    () => {
      incorporarPropuestas();
      return esperar(pagina([...pendientesMock]));
    },
  );
}

export function decidir(eventoId: string, decision: Decision): Promise<Evento> {
  return llamar(
    () => peticion(`/moderacion/${eventoId}/decision`, { method: 'POST', body: JSON.stringify(decision) }),
    () => {
      const i = pendientesMock.findIndex((p) => p.evento?.id === eventoId);
      const e = i >= 0 ? pendientesMock[i].evento! : todosLosEventos().find((x) => x.id === eventoId);
      if (!e) return Promise.reject(new Error('evento_no_encontrado'));
      if (i >= 0) pendientesMock.splice(i, 1);
      e.moderacion = { ...e.moderacion, motivo: decision.motivo ?? null, revisado_por: 'moderador' };
      if (decision.decision === 'aprobar') pasarAPublicado(e);
      else {
        e.estado = decision.decision === 'rechazar' ? 'rechazado' : 'archivado';
        const j = mockEventos.findIndex((x) => x.id === e.id);
        if (j >= 0) mockEventos.splice(j, 1);
        if (!eventosInternos.includes(e)) eventosInternos.push(e);
      }
      return esperar(e);
    },
  );
}

// ---------- publicadores ----------
export function getPublicadores(): Promise<Pagina<Publicador>> {
  return llamar(
    () => peticion('/publicadores?size=100'),
    () => esperar(pagina([...publicadoresMock])),
  );
}

export function aprobarPublicador(
  id: string,
  cuerpo: { aprobar: boolean; nivel_confianza?: 0 | 1 | 2; motivo?: string | null },
): Promise<Publicador> {
  return llamar(
    () => peticion(`/publicadores/${id}/aprobar`, { method: 'POST', body: JSON.stringify(cuerpo) }),
    () => {
      const p = publicadoresMock.find((x) => x.id === id);
      if (!p) return Promise.reject(new Error('publicador_no_encontrado'));
      p.estado = cuerpo.aprobar ? 'aprobado' : 'rechazado';
      p.nivel_confianza = cuerpo.nivel_confianza ?? p.nivel_confianza;
      const i = pendientesMock.findIndex((x) => x.publicador?.id === id);
      if (i >= 0) pendientesMock.splice(i, 1);
      return esperar({ ...p });
    },
  );
}

export function pausarPublicador(
  id: string,
  cuerpo: { que: 'publicador' | 'automatizaciones'; pausado: boolean },
): Promise<Publicador> {
  return llamar(
    () => peticion(`/publicadores/${id}/pausar`, { method: 'POST', body: JSON.stringify(cuerpo) }),
    () => {
      const p = publicadoresMock.find((x) => x.id === id);
      if (!p) return Promise.reject(new Error('publicador_no_encontrado'));
      if (cuerpo.que === 'automatizaciones') p.automatizaciones_pausadas = cuerpo.pausado;
      else p.estado = cuerpo.pausado ? 'pausado' : 'aprobado';
      return esperar({ ...p });
    },
  );
}

// ---------- eventos ----------
export function getEventosAdmin(
  filtros: { estado?: EstadoEvento; publicador_id?: string } = {},
): Promise<Pagina<Evento>> {
  return llamar(
    () => peticion(`/eventos${query({ size: 100, ...filtros })}`),
    () => {
      incorporarPropuestas();
      let items = todosLosEventos();
      if (filtros.estado) items = items.filter((e) => e.estado === filtros.estado);
      if (filtros.publicador_id) items = items.filter((e) => e.publicador_id === filtros.publicador_id);
      // Primero lo que viene, por fecha; lo ya pasado, al final.
      const hoy = new Date().toISOString();
      items.sort(
        (a, b) =>
          Number(a.fecha_inicio < hoy) - Number(b.fecha_inicio < hoy) || a.fecha_inicio.localeCompare(b.fecha_inicio),
      );
      return esperar(pagina(items));
    },
  );
}

/**
 * Crea un evento desde el panel. El moderador publica directamente; un publicador de nivel 2 también,
 * y uno de nivel 0 o 1 lo deja en la bandeja (en la API real esto lo decide A).
 */
export function crearEvento(datos: EventoCrear, autor: { rol: 'moderador' | 'publicador' }): Promise<Evento> {
  return llamar(
    () => peticion('/eventos', { method: 'POST', body: JSON.stringify(datos) }),
    () => {
      const pub = publicadoresMock.find((p) => p.id === datos.publicador_id);
      if (pub?.estado === 'pausado')
        return Promise.reject(new Error('Este publicador está pausado por el ayuntamiento y no puede publicar.'));
      const e = nuevoEventoMock({
        ...datos,
        lat: datos.lat ?? undefined,
        lon: datos.lon ?? undefined,
        es_gratuito: datos.es_gratuito ?? !datos.precio_eur,
        plazas_libres: datos.plazas_totales ?? null,
        publicador_nombre: pub?.nombre ?? 'Ayuntamiento',
        origen: { canal: 'panel', url: null, importado_auto: false },
      });
      if (autor.rol === 'moderador' || pub?.nivel_confianza === 2) pasarAPublicado(e);
      else
        pendientesMock.push({
          tipo: 'evento',
          motivo: `Publicador de nivel ${pub?.nivel_confianza ?? 0}: sus planes se revisan a mano.`,
          score_spam: 0.02,
          evento: e,
        });
      return esperar(e);
    },
  );
}

export function editarEvento(id: string, cambios: EventoEditar): Promise<Evento> {
  return llamar(
    () => peticion(`/eventos/${id}`, { method: 'PATCH', body: JSON.stringify(cambios) }),
    () => {
      const e = todosLosEventos().find((x) => x.id === id);
      if (!e) return Promise.reject(new Error('evento_no_encontrado'));
      Object.assign(e, cambios, { actualizado_en: new Date().toISOString() });
      if (cambios.estado) {
        const j = mockEventos.findIndex((x) => x.id === e.id);
        if (j >= 0) mockEventos.splice(j, 1);
        if (!eventosInternos.includes(e)) eventosInternos.push(e);
      }
      return esperar({ ...e });
    },
  );
}

// ---------- panel ----------
export function getEstadisticas(): Promise<Estadisticas> {
  return llamar(
    () => peticion('/estadisticas'),
    () => {
      const publicados = mockEventos.filter((e) => e.estado === 'publicado').length;
      return esperar({ ...estadisticasMock, actividades: publicados });
    },
  );
}
