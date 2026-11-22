// Llamadas de la interfaz del ayuntamiento (moderador y publicador), todas con la sesión (JWT) del usuario.
// Con sesión real de moderador o publicador van a la API; si la API no responde, se vuelve a los mocks.
// Solo si no hay API (o no tiene DEMO_MODE para entrar sin cuenta) se usa el modo demo, todo con mocks.

import { puedeSerAutomatica, type ModoRevision } from '../admin/confianza';
import { COORDENADAS, estadisticasMock, nuevoEventoMock, pendientesMock, publicadoresMock } from '../mocks/admin';

import { conRespaldo, ErrorApi, esperar, mockEventos, peticion, propuestasMock, query, USAR_MOCKS } from './client';
import type {
  BorradorSugerencia,
  CaidaSimulada,
  Decision,
  EstadoEvento,
  Estadisticas,
  Evento,
  EventoCrear,
  MetricasBot,
  EventoEditar,
  Pagina,
  PendienteBandeja,
  PublicadorAdmin,
  Rol,
  Sugerencias,
  Token,
} from './types';

// Usuarios de la demo en contracts/fixtures/usuarios.json: Lucía (moderadora) y Antonio (Ayto. de Velefique desde el 22/11,
// con revisión a mano, así sus planes pasan por la bandeja).
const USUARIOS_DEMO: Record<'moderador' | 'publicador', string> = {
  moderador: '5a5e0000-0000-4000-8000-000000000002',
  publicador: '5a5e0000-0000-4000-8000-000000000003',
};

/**
 * Entra sin cuenta como el moderador o el publicador de la demo (`POST /auth/demo`, solo con DEMO_MODE=true en la
 * API). Devuelve null si no hay API o no está en modo demo: entonces la zona del ayuntamiento va con mocks.
 */
export async function entrarDemo(rol: 'moderador' | 'publicador'): Promise<Token | null> {
  if (USAR_MOCKS) return null;
  const pedir = (cuerpo: { usuario_id?: string; rol?: Rol }) =>
    peticion<Token>('/auth/demo', { method: 'POST', body: JSON.stringify(cuerpo) });
  try {
    return await pedir({ usuario_id: USUARIOS_DEMO[rol] });
  } catch (e) {
    // Si alguien ha cambiado los usuarios de la demo, vale el primero con ese rol.
    if (e instanceof ErrorApi && e.code === 'usuario_no_encontrado') return pedir({ rol }).catch(() => null);
    return null;
  }
}

/**
 * Acceso de la moderación del ayuntamiento con usuario y contraseña (`POST /auth/admin`; en la API,
 * ADMIN_USUARIO / ADMIN_CONTRASENA del .env). Lanza ErrorApi `credenciales_invalidas` si no coinciden.
 */
export function entrarAdmin(usuario: string, contrasena: string): Promise<Token> {
  return peticion<Token>('/auth/admin', { method: 'POST', body: JSON.stringify({ usuario, contrasena }) });
}

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
    async () => {
      const r = await peticion<Pagina<PendienteBandeja>>('/moderacion/pendientes?size=100');
      // La API manda los datos privados de una propuesta vecinal dentro del evento.
      const items = r.items.map((p) =>
        p.evento?.datos_ayuntamiento && !p.propuesta
          ? { ...p, propuesta: p.evento.datos_ayuntamiento as PendienteBandeja['propuesta'] }
          : p,
      );
      return { ...r, items };
    },
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
      if (decision.decision === 'restaurar') {
        e.estado = 'en_revision';
        e.moderacion = { ...e.moderacion, motivo: 'Restaurado por moderación: pendiente de revisar de nuevo' };
        const j = eventosInternos.indexOf(e);
        if (j >= 0) eventosInternos.splice(j, 1);
        pendientesMock.push({ tipo: 'evento', motivo: 'Restaurado tras un rechazo', score_spam: null, evento: e });
        return esperar(e);
      }
      if (i >= 0) pendientesMock.splice(i, 1);
      e.moderacion = { ...e.moderacion, motivo: decision.motivo ?? null, revisado_por: 'moderador' };
      contarEnActividad(e.publicador_id, decision.decision === 'aprobar');
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

// La frecuencia y los rechazos cuentan para pasar a revisión automática (en la API real los calcula A).
function contarEnActividad(publicadorId: string | null | undefined, aprobado: boolean) {
  const p = publicadoresMock.find((x) => x.id === publicadorId);
  if (!p) return;
  const a = p.actividad ?? { planes_60_dias: 0, rechazados_60_dias: 0, ultimo_plan: null };
  p.actividad = aprobado
    ? { ...a, planes_60_dias: a.planes_60_dias + 1, ultimo_plan: new Date().toISOString() }
    : { ...a, rechazados_60_dias: a.rechazados_60_dias + 1 };
}

// ---------- publicadores ----------
export function getPublicadores(): Promise<Pagina<PublicadorAdmin>> {
  return llamar(
    () => peticion('/publicadores?size=100'),
    () => esperar(pagina([...publicadoresMock])),
  );
}

export function aprobarPublicador(
  id: string,
  cuerpo: { aprobar: boolean; motivo?: string | null },
): Promise<PublicadorAdmin> {
  return llamar(
    // Toda asociación nueva empieza con revisión a mano (nivel 0).
    () =>
      peticion(`/publicadores/${id}/aprobar`, {
        method: 'POST',
        body: JSON.stringify({ ...cuerpo, nivel_confianza: 0 }),
      }),
    () => {
      const p = publicadoresMock.find((x) => x.id === id);
      if (!p) return Promise.reject(new Error('publicador_no_encontrado'));
      p.estado = cuerpo.aprobar ? 'aprobado' : 'rechazado';
      p.nivel_confianza = 0;
      const i = pendientesMock.findIndex((x) => x.publicador?.id === id);
      if (i >= 0) pendientesMock.splice(i, 1);
      return esperar({ ...p });
    },
  );
}

export function pausarPublicador(
  id: string,
  cuerpo: { que: 'publicador' | 'automatizaciones'; pausado: boolean },
): Promise<PublicadorAdmin> {
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

/**
 * Pasa a revisión automática (nivel 2) o a mano (nivel 0). En el contrato no hay ruta propia:
 * se usa /publicadores/{id}/aprobar con el nuevo nivel. A tiene que aceptarlo en un publicador ya aprobado.
 */
export function cambiarRevision(id: string, modo: ModoRevision): Promise<PublicadorAdmin> {
  const nivel = modo === 'automatica' ? 2 : 0;
  return llamar(
    () =>
      peticion(`/publicadores/${id}/aprobar`, {
        method: 'POST',
        body: JSON.stringify({ aprobar: true, nivel_confianza: nivel }),
      }),
    () => {
      const p = publicadoresMock.find((x) => x.id === id);
      if (!p) return Promise.reject(new Error('publicador_no_encontrado'));
      if (modo === 'automatica' && !puedeSerAutomatica(p))
        return Promise.reject(new Error(`${p.nombre} aún no cumple los requisitos para publicar sin revisión.`));
      p.nivel_confianza = nivel;
      return esperar({ ...p });
    },
  );
}

/** El moderador marca como comprobados el DNI y la residencia del responsable. */
export function verificarIdentidad(id: string): Promise<PublicadorAdmin> {
  return llamar(
    () =>
      peticion(`/publicadores/${id}/verificar-identidad`, {
        method: 'POST',
        body: JSON.stringify({ identidad_verificada: true }),
      }),
    () => {
      const p = publicadoresMock.find((x) => x.id === id);
      if (!p?.responsable) return Promise.reject(new Error('Falta que el responsable aporte sus datos.'));
      p.responsable = { ...p.responsable, identidad_verificada: true };
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
 * Crea un evento desde el panel. El moderador publica directamente; una asociación con revisión automática
 * también, y una con revisión a mano lo deja en la bandeja (en la API real esto lo decide A).
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
          motivo: `Revisión a mano: ${pub?.nombre ?? 'esta asociación'} aún no cumple los requisitos para publicar sin revisión.`,
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

// ---------- N7: ideas de la IA para el moderador ----------
// La API elige los planes con más participación y el bot propone otros parecidos; si el bot no está, propone por reglas.
function sugerenciasMock(): Sugerencias {
  const base = [...mockEventos].sort((a, b) => (b.plazas_totales ?? 0) - (a.plazas_totales ?? 0)).slice(0, 2);
  return {
    proveedor_ia: 'reglas',
    basado_en: base.map((e) => ({
      evento_id: e.id,
      titulo: e.titulo,
      categoria: e.categoria,
      municipio: e.municipio,
      fecha_inicio: e.fecha_inicio,
      plazas_totales: e.plazas_totales ?? null,
      inscritos: (e.plazas_totales ?? 0) - (e.plazas_libres ?? 0),
      lista_espera: 0,
      preguntas_chat: 0,
      ocupacion: e.plazas_totales ? ((e.plazas_totales ?? 0) - (e.plazas_libres ?? 0)) / e.plazas_totales : null,
    })),
    items: base.map((e) => ({
      titulo: `Otra edición: ${e.titulo}`,
      descripcion: e.descripcion ?? null,
      categoria: e.categoria,
      municipio: e.municipio,
      fecha_aproximada: 'dentro de unos meses',
      motivo: 'Es de los planes con más gente apuntada (modo demo, sin IA).',
      basado_en: [e.id],
    })),
  };
}

export function getSugerencias(): Promise<Sugerencias> {
  return llamar(
    () => peticion('/admin/sugerencias'),
    () => esperar(sugerenciasMock()),
  );
}

/** [Crear borrador]: la propuesta entra en la bandeja (`en_revision`) con la fecha que elige el moderador. */
export function crearBorradorSugerencia(borrador: BorradorSugerencia): Promise<Evento> {
  return llamar(
    () => peticion('/admin/sugerencias/borrador', { method: 'POST', body: JSON.stringify(borrador) }),
    () => {
      const e = nuevoEventoMock({
        titulo: borrador.titulo,
        descripcion: borrador.descripcion ?? '',
        categoria: borrador.categoria,
        municipio: borrador.municipio,
        fecha_inicio: borrador.fecha_inicio,
        estado: 'en_revision',
        publicador_nombre: 'Ayuntamiento',
        origen: { canal: 'panel', url: null, importado_auto: false },
      });
      pendientesMock.unshift({
        tipo: 'evento',
        motivo: `Propuesto por la IA: ${borrador.motivo}`,
        score_spam: null,
        evento: e,
      });
      return esperar(e);
    },
  );
}

// ---------- robustez del bot (la API hace de intermediaria: el INTERNAL_TOKEN no llega al navegador) ----------
let caidaMock = false;

function metricasMock(): MetricasBot {
  return {
    totales: Object.fromEntries(
      Object.entries(estadisticasMock.tokens?.por_proveedor ?? {}).map(([n, p]) => [
        n,
        { llamadas: p.llamadas ?? 0, entrada: p.entrada ?? 0, salida: p.salida ?? 0, fallos: 0 },
      ]),
    ),
    ultimas: [],
    eventos_en_cola: 0,
    caida_simulada: caidaMock,
  };
}

/**
 * Métricas del bot (`GET /admin/bot/metricas`). Aquí no se vuelve a los mocks: si el bot no responde
 * (503 `bot_no_disponible`), el panel lo tiene que decir.
 */
export function getMetricasBot(): Promise<MetricasBot> {
  return demo ? esperar(metricasMock()) : peticion('/admin/bot/metricas');
}

/** Activa o quita la caída simulada de todas las IAs: el bot sigue solo con reglas. */
export function simularCaida(activa: boolean): Promise<CaidaSimulada> {
  if (!demo) return peticion('/admin/bot/simular-caida', { method: 'POST', body: JSON.stringify({ activa }) });
  caidaMock = activa;
  return esperar({ activa });
}
