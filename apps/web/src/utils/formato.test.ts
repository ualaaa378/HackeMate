import { describe, expect, it } from 'vitest';

import { yaPaso } from './formato';

const ahora = new Date('2026-11-21T12:00:00+01:00');

describe('yaPaso', () => {
  it('un plan finalizado siempre ha pasado', () => {
    expect(yaPaso({ estado: 'finalizado', fecha_inicio: '2027-01-01T10:00:00+01:00' }, ahora)).toBe(true);
  });
  it('con hora de fin, mira esa hora', () => {
    expect(
      yaPaso(
        { estado: 'publicado', fecha_inicio: '2026-11-21T09:00:00+01:00', fecha_fin: '2026-11-21T11:00:00+01:00' },
        ahora,
      ),
    ).toBe(true);
    expect(
      yaPaso(
        { estado: 'publicado', fecha_inicio: '2026-11-21T09:00:00+01:00', fecha_fin: '2026-11-21T14:00:00+01:00' },
        ahora,
      ),
    ).toBe(false);
  });
  it('sin hora de fin, dura hasta el final de su día', () => {
    expect(yaPaso({ estado: 'publicado', fecha_inicio: '2026-11-21T09:00:00+01:00' }, ahora)).toBe(false);
    expect(yaPaso({ estado: 'publicado', fecha_inicio: '2026-11-20T18:00:00+01:00' }, ahora)).toBe(true);
  });
});
