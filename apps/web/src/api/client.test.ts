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

  it('pasa a la pantalla los errores de negocio', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      respuesta(404, { error: { code: 'evento_no_encontrado', message: 'No existe', details: {} } }),
    );
    const { getEvento } = await cargarCliente();
    await expect(getEvento('nada')).rejects.toMatchObject({ code: 'evento_no_encontrado', status: 404 });
  });
});
