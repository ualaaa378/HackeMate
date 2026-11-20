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

describe('isoMadrid', () => {
  it('usa +01:00 en invierno y +02:00 en verano', async () => {
    const { isoMadrid } = await import('../utils/formato');
    expect(isoMadrid('2026-11-28', '18:30')).toBe('2026-11-28T18:30:00+01:00');
    expect(isoMadrid('2026-07-15', '21:00')).toBe('2026-07-15T21:00:00+02:00');
  });
});
