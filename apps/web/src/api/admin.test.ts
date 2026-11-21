import { beforeEach, describe, expect, it, vi } from 'vitest';

// Sin VITE_API_URL todo va con mocks; se recargan los módulos para empezar cada prueba con la bandeja llena.
async function cargar() {
  vi.resetModules();
  const admin = await import('./admin');
  const client = await import('./client');
  admin.setAdminDemo(true);
  return { ...admin, ...client };
}

describe('interfaz del ayuntamiento en modo demo', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_URL', '');
  });

  it('rechazar el caso de las apuestas lo quita de la bandeja y no sale en la agenda', async () => {
    const api = await cargar();
    const { items } = await api.getPendientes();
    const apuestas = items.find((p) => p.evento?.titulo.includes('apuestas'))!;
    expect(apuestas.score_spam).toBeGreaterThan(0.7);

    await api.decidir(apuestas.evento!.id, { decision: 'rechazar', motivo: 'Apuestas' });

    const despues = await api.getPendientes();
    expect(despues.items.some((p) => p.evento?.id === apuestas.evento!.id)).toBe(false);
    const agenda = await api.getEventos({ size: 200 });
    expect(agenda.items.some((e) => e.id === apuestas.evento!.id)).toBe(false);
    const rechazados = await api.getEventosAdmin({ estado: 'rechazado' });
    expect(rechazados.items.map((e) => e.id)).toContain(apuestas.evento!.id);
  });

  it('restaurar un rechazado lo devuelve a la bandeja', async () => {
    const api = await cargar();
    const apuestas = (await api.getPendientes()).items.find((p) => p.evento?.titulo.includes('apuestas'))!.evento!;
    await api.decidir(apuestas.id, { decision: 'rechazar' });

    const restaurado = await api.decidir(apuestas.id, { decision: 'restaurar' });

    expect(restaurado.estado).toBe('en_revision');
    expect((await api.getPendientes()).items.some((p) => p.evento?.id === apuestas.id)).toBe(true);
    const rechazados = await api.getEventosAdmin({ estado: 'rechazado' });
    expect(rechazados.items.map((e) => e.id)).not.toContain(apuestas.id);
  });

  it('aprobar un evento lo publica en la agenda y en su ficha', async () => {
    const api = await cargar();
    const { items } = await api.getPendientes();
    const concierto = items.find((p) => p.evento?.titulo.includes('banda'))!.evento!;

    await api.decidir(concierto.id, { decision: 'aprobar' });

    const agenda = await api.getEventos({ size: 200 });
    expect(agenda.items.map((e) => e.id)).toContain(concierto.id);
    expect((await api.getEvento(concierto.id)).estado).toBe('publicado');
  });

  it('una propuesta vecinal entra en la bandeja con sus datos para el ayuntamiento', async () => {
    const api = await cargar();
    await api.proponerEvento(
      {
        titulo: 'Taller de bolillos',
        categoria: 'cultural',
        municipio: 'Tahal',
        fecha_inicio: '2026-11-30T17:00:00+01:00',
      },
      {
        responsable: 'Pepa',
        telefono: '+34600000999',
        entidad: 'particular',
        publico: 'mayores',
        necesidades: ['espacio'],
        seguro_rc: 'no',
      },
    );
    const { items } = await api.getPendientes();
    const propuesta = items.find((p) => p.evento?.titulo === 'Taller de bolillos')!;
    expect(propuesta.propuesta?.responsable).toBe('Pepa');
    expect(propuesta.evento!.lat).not.toBe(0);
  });

  it('un publicador pausado no puede crear planes', async () => {
    const api = await cargar();
    const { items } = await api.getPublicadores();
    const bar = items.find((p) => p.nombre === 'Bar La Plaza')!;
    await api.pausarPublicador(bar.id, { que: 'publicador', pausado: true });
    await expect(
      api.crearEvento(
        {
          titulo: 'Tapeo',
          categoria: 'gastronomia',
          municipio: 'Senés',
          fecha_inicio: '2026-11-28T13:00:00+01:00',
          publicador_id: bar.id,
        },
        { rol: 'publicador' },
      ),
    ).rejects.toThrow(/pausado/);
  });

  it('un publicador de nivel 1 deja su plan en la bandeja; el moderador publica directo', async () => {
    const api = await cargar();
    const base = { categoria: 'deportiva' as const, municipio: 'Velefique', fecha_inicio: '2026-12-05T09:00:00+01:00' };
    const deAsociacion = await api.crearEvento(
      { ...base, titulo: 'Ruta de la asociación', publicador_id: '7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01' },
      { rol: 'publicador' },
    );
    const delAyto = await api.crearEvento({ ...base, titulo: 'Ruta del ayuntamiento' }, { rol: 'moderador' });
    expect(deAsociacion.estado).toBe('en_revision');
    expect(delAyto.estado).toBe('publicado');
  });
});

describe('revisión a mano o automática', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_API_URL', '');
  });

  it('una asociación sin DNI comprobado o con pocos planes no puede publicar sin revisión', async () => {
    const api = await cargar();
    const { puedeSerAutomatica } = await import('../admin/confianza');
    const { items } = await api.getPublicadores();
    const mujeres = items.find((p) => p.nombre === 'Asociación de Mujeres de Senés')!;
    const amigos = items.find((p) => p.nombre === 'Amigos de Velefique')!;
    expect(puedeSerAutomatica(mujeres)).toBe(false); // DNI aportado pero sin comprobar
    expect(puedeSerAutomatica(amigos)).toBe(false); // solo 2 de 3 planes
    await expect(api.cambiarRevision(mujeres.id, 'automatica')).rejects.toThrow(/requisitos/);

    const verificada = await api.verificarIdentidad(mujeres.id);
    expect(puedeSerAutomatica(verificada)).toBe(true);
    expect((await api.cambiarRevision(mujeres.id, 'automatica')).nivel_confianza).toBe(2);
  });

  it('aprobar un plan cuenta para la frecuencia', async () => {
    const api = await cargar();
    const { puedeSerAutomatica } = await import('../admin/confianza');
    const amigos = (await api.getPublicadores()).items.find((p) => p.nombre === 'Amigos de Velefique')!;
    const plan = await api.crearEvento(
      {
        titulo: 'Ruta nocturna',
        categoria: 'deportiva',
        municipio: 'Velefique',
        fecha_inicio: '2026-12-12T19:00:00+01:00',
        publicador_id: amigos.id,
      },
      { rol: 'publicador' },
    );
    await api.decidir(plan.id, { decision: 'aprobar' });
    const despues = (await api.getPublicadores()).items.find((p) => p.id === amigos.id)!;
    expect(despues.actividad?.planes_60_dias).toBe(3);
    expect(puedeSerAutomatica(despues)).toBe(true);
  });

  it('rechazar las apuestas deja a Bar La Plaza pendiente de volver a revisión a mano', async () => {
    const api = await cargar();
    const { deberiaVolverAManual } = await import('../admin/confianza');
    const apuestas = (await api.getPendientes()).items.find((p) => p.evento?.titulo.includes('apuestas'))!;
    await api.decidir(apuestas.evento!.id, { decision: 'rechazar' });
    const bar = (await api.getPublicadores()).items.find((p) => p.nombre === 'Bar La Plaza')!;
    expect(deberiaVolverAManual(bar)).toBe(true);
    expect((await api.cambiarRevision(bar.id, 'manual')).nivel_confianza).toBe(0);
  });

  it('el DNI nunca sale entero', async () => {
    const { dniOculto } = await import('../admin/confianza');
    expect(dniOculto('45871236J')).toBe('•••••236J');
  });
});

describe('isoMadrid', () => {
  it('usa +01:00 en invierno y +02:00 en verano', async () => {
    const { isoMadrid } = await import('../utils/formato');
    expect(isoMadrid('2026-11-28', '18:30')).toBe('2026-11-28T18:30:00+01:00');
    expect(isoMadrid('2026-07-15', '21:00')).toBe('2026-07-15T21:00:00+02:00');
  });
});

describe('interfaz del ayuntamiento con la API real', () => {
  const respuestas = new Map<string, unknown>();
  const llamadas: { ruta: string; cuerpo: unknown; auth: string | undefined }[] = [];

  beforeEach(() => {
    vi.stubEnv('VITE_API_URL', 'http://api.test');
    respuestas.clear();
    llamadas.length = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init: RequestInit = {}) => {
        const ruta = url.replace('http://api.test/api/v1', '');
        const cabeceras = init.headers as Record<string, string>;
        llamadas.push({
          ruta,
          cuerpo: init.body ? JSON.parse(init.body as string) : null,
          auth: cabeceras.Authorization,
        });
        const r = respuestas.get(ruta.split('?')[0]);
        const err = r === undefined;
        return Promise.resolve(
          new Response(JSON.stringify(err ? { error: { code: 'no_encontrado', message: 'x' } } : r), {
            status: err ? 404 : 200,
          }),
        );
      }),
    );
  });

  async function cargarReal() {
    vi.resetModules();
    const admin = await import('./admin');
    const client = await import('./client');
    admin.setAdminDemo(false);
    client.setToken('jwt-moderador');
    return { ...admin, ...client };
  }

  it('entrar en la demo pide sesión al usuario de la demo de ese rol', async () => {
    const api = await cargarReal();
    const token = { access_token: 't', token_type: 'bearer', usuario: { id: 'u', nombre: 'Lucía', rol: 'moderador' } };
    respuestas.set('/auth/demo', token);
    expect(await api.entrarDemo('moderador')).toEqual(token);
    expect(llamadas[0].cuerpo).toEqual({ usuario_id: '5a5e0000-0000-4000-8000-000000000002' });
  });

  it('sin DEMO_MODE en la API, la entrada de la demo vuelve a los mocks', async () => {
    const api = await cargarReal();
    expect(await api.entrarDemo('publicador')).toBeNull();
  });

  it('la bandeja enseña los datos privados de la propuesta vecinal que manda la API dentro del evento', async () => {
    const api = await cargarReal();
    const privados = { responsable: 'Carmen', telefono: '600000000', entidad: 'particular' };
    respuestas.set('/moderacion/pendientes', {
      items: [{ tipo: 'evento', motivo: 'Propuesta vecinal', evento: { id: 'e1', datos_ayuntamiento: privados } }],
      total: 1,
      page: 1,
      size: 100,
    });
    const { items } = await api.getPendientes();
    expect(items[0].propuesta).toEqual(privados);
    expect(llamadas[0].auth).toBe('Bearer jwt-moderador');
  });

  it('la propuesta vecinal va a POST /eventos con sus datos privados y la frase aparte', async () => {
    const api = await cargarReal();
    api.setToken('jwt-vecina');
    respuestas.set('/eventos', { id: 'e2', titulo: 'Taller', estado: 'en_revision' });
    const r = await api.proponerEvento(
      { titulo: 'Taller', categoria: 'cultural', municipio: 'Senés', fecha_inicio: '2026-11-28T11:00:00+01:00' },
      {
        responsable: 'Carmen',
        telefono: '600000000',
        entidad: 'particular',
        publico: 'todos',
        necesidades: [],
        seguro_rc: 'nose',
        frase_portada: '¡Ven a aprender!',
      },
    );
    expect(r.demo).toBe(false);
    const cuerpo = llamadas[0].cuerpo as Record<string, unknown>;
    expect(cuerpo.frase_portada).toBe('¡Ven a aprender!');
    expect(cuerpo.datos_ayuntamiento).not.toHaveProperty('frase_portada');
    expect(cuerpo.datos_ayuntamiento).toMatchObject({ responsable: 'Carmen' });
  });

  it('simular la caída de la IA pasa por la API y no se finge si el bot no responde', async () => {
    const api = await cargarReal();
    respuestas.set('/admin/bot/simular-caida', { activa: true });
    expect(await api.simularCaida(true)).toEqual({ activa: true });
    expect(llamadas[0].cuerpo).toEqual({ activa: true });
    await expect(api.getMetricasBot()).rejects.toThrow();
  });
});
