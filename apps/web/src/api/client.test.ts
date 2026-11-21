import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// client.ts lee VITE_API_URL al importarse: se importa de nuevo en cada prueba.
async function cargarCliente() {
  vi.resetModules();
  return import('./client');
}

function respuesta(status: number, cuerpo: unknown) {
  return Promise.resolve(new Response(JSON.stringify(cuerpo), { status }));
}

describe('client con la API real', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_URL', 'http://api.test');
    vi.stubEnv('VITE_USE_MOCKS', 'false');
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('usa los datos de la API cuando responde', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      respuesta(200, { items: [{ id: 'x' }], total: 1, page: 1, size: 100 }),
    );
    const { getEventos, enModoRespaldo } = await cargarCliente();
    const pagina = await getEventos();
    expect(pagina.total).toBe(1);
    expect(enModoRespaldo()).toBe(false);
  });

  it('pide «Para ti» a la API con el usuario y devuelve los items', async () => {
    const fetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() =>
        respuesta(200, { items: [{ evento: { id: 'e1' }, puntuacion: 0.9, motivo: 'Te gusta' }] }),
      );
    const { getRecomendaciones } = await cargarCliente();
    const recs = await getRecomendaciones('u1');
    expect(recs[0].motivo).toBe('Te gusta');
    expect(String(fetch.mock.calls[0][0])).toContain('/api/v1/recomendaciones?usuario_id=u1');
  });

  it('vuelve a los mocks si la API no responde', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    const { getEventos, enModoRespaldo } = await cargarCliente();
    const pagina = await getEventos();
    expect(pagina.total).toBeGreaterThan(0);
    expect(enModoRespaldo()).toBe(true);
  });

  it('vuelve a los mocks si la ruta aún no existe en la API', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      respuesta(404, { error: { code: 'no_encontrado', message: 'Not Found', details: {} } }),
    );
    const { inscribirse } = await cargarCliente();
    const insc = await inscribirse('cualquiera');
    expect(['confirmada', 'lista_espera']).toContain(insc.estado);
  });

  it('cierra la sesión que ya no vale y repite la petición sin token', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_url, init) => {
      const cabeceras = (init?.headers ?? {}) as Record<string, string>;
      return cabeceras.Authorization
        ? respuesta(401, {
            error: { code: 'token_invalido', message: 'El usuario de la sesión ya no existe', details: {} },
          })
        : respuesta(200, { id: 'ruta', titulo: 'Ruta' });
    });
    const { getEvento, setToken, alCaducarSesion } = await cargarCliente();
    const caducada = vi.fn();
    alCaducarSesion(caducada);
    setToken('token-viejo');
    const evento = await getEvento('ruta');
    expect(evento.id).toBe('ruta');
    expect(caducada).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await getEvento('ruta');
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('pasa a la pantalla los errores de negocio', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      respuesta(404, { error: { code: 'evento_no_encontrado', message: 'No existe', details: {} } }),
    );
    const { getEvento } = await cargarCliente();
    await expect(getEvento('nada')).rejects.toMatchObject({ code: 'evento_no_encontrado', status: 404 });
  });
});

describe('planes que ya han pasado (mocks)', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('no deja apuntarse ni preguntar, pero sí comentar con foto', async () => {
    const { getEventosPasados, inscribirse, enviarMensaje, getMensajes } = await cargarCliente();
    const [pasado] = await getEventosPasados(new Date('2026-11-21T12:00:00+01:00'));
    const autor = { id: '00000000-0000-4000-8000-000000000009', nombre: 'Vecina' };
    await expect(inscribirse(pasado.id)).rejects.toMatchObject({ code: 'evento_finalizado' });
    await expect(enviarMensaje(pasado.id, { texto: '¿A qué hora?', tipo: 'pregunta' }, autor)).rejects.toMatchObject({
      code: 'evento_finalizado',
    });
    await enviarMensaje(
      pasado.id,
      { texto: 'Qué bonito', tipo: 'comentario', imagen_url: 'data:image/webp;base64,AA' },
      autor,
    );
    const { items } = await getMensajes(pasado.id);
    expect(items.at(-1)).toMatchObject({ tipo: 'comentario', imagen_url: 'data:image/webp;base64,AA' });
  });
});

describe('client con la API en el mismo dominio (VITE_API_URL=/)', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_URL', '/');
    vi.stubEnv('VITE_USE_MOCKS', 'false');
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('no usa los mocks y llama a rutas relativas', async () => {
    const fetchEspia = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(() => respuesta(200, { items: [], total: 0, page: 1, size: 100 }));
    const { getEventos, USAR_MOCKS, urlIcs } = await cargarCliente();
    expect(USAR_MOCKS).toBe(false);
    await getEventos();
    expect(String(fetchEspia.mock.calls[0][0])).toMatch(/^\/api\/v1\/eventos/);
    expect(urlIcs('abc')).toBe('/api/v1/eventos/abc/ics');
  });

  it('sin VITE_API_URL sigue usando los mocks', async () => {
    vi.stubEnv('VITE_API_URL', '');
    const { USAR_MOCKS } = await cargarCliente();
    expect(USAR_MOCKS).toBe(true);
  });
});
