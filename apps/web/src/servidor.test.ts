import { afterEach, describe, expect, it, vi } from 'vitest';

import { direccionGuardada, guardarDireccion, normalizarDireccion } from './servidor';

describe('dirección del servidor (APK)', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('normaliza lo que se pega', () => {
    expect(normalizarDireccion('  algo.trycloudflare.com/ ')).toBe('https://algo.trycloudflare.com');
    expect(normalizarDireccion('http://192.168.1.10:8080')).toBe('http://192.168.1.10:8080');
    expect(normalizarDireccion('')).toBe('');
    expect(normalizarDireccion('no es una url')).toBe('');
  });

  it('se guarda y se quita', () => {
    guardarDireccion('https://a.trycloudflare.com');
    expect(direccionGuardada()).toBe('https://a.trycloudflare.com');
    guardarDireccion('');
    expect(direccionGuardada()).toBe('');
  });

  it('la dirección guardada manda sobre la de la build y desactiva los mocks', async () => {
    vi.stubEnv('VITE_API_URL', '/');
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    guardarDireccion('https://a.trycloudflare.com');
    const llamadas: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        llamadas.push(url);
        return new Response(JSON.stringify({ items: [], total: 0, page: 1, size: 20 }), { status: 200 });
      }),
    );
    const client = await import('./api/client');
    expect(client.USAR_MOCKS).toBe(false);
    await client.peticion('/municipios');
    expect(llamadas[0]).toBe('https://a.trycloudflare.com/api/v1/municipios');
    vi.unstubAllGlobals();
  });
});

describe('APK sin dirección guardada', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('un 200 con HTML (la propia app o el túnel) cae a los mocks', async () => {
    vi.stubEnv('VITE_API_URL', '/');
    vi.stubEnv('VITE_USE_MOCKS', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<!doctype html><html></html>', { status: 200 })),
    );
    const client = await import('./api/client');
    const pagina = await client.conRespaldo(
      () => client.peticion<{ total: number }>('/eventos'),
      async () => ({ total: -1 }),
    );
    expect(pagina.total).toBe(-1);
    expect(client.enModoRespaldo()).toBe(true);
  });
});
