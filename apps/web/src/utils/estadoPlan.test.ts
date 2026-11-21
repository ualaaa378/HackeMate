import { describe, expect, it } from 'vitest';

import { estadoPlan } from './estadoPlan';

const ahora = new Date('2026-11-21T22:00:00+01:00');
const plan = (estado: string, fecha_inicio = '2026-12-05T10:00:00+01:00') =>
  ({ estado, fecha_inicio, fecha_fin: null }) as Parameters<typeof estadoPlan>[0];

describe('estadoPlan (P5c)', () => {
  it('en revisión y publicado se pueden modificar', () => {
    expect(estadoPlan(plan('en_revision'), ahora)).toMatchObject({ clase: 'revision', modificable: true });
    expect(estadoPlan(plan('pendiente_confirmacion'), ahora)).toMatchObject({ clase: 'revision' });
    expect(estadoPlan(plan('publicado'), ahora)).toMatchObject({ clase: 'publicado', modificable: true });
  });

  it('un publicado que ya pasó cuenta como ya hecho', () => {
    expect(estadoPlan(plan('publicado', '2026-11-10T10:00:00+01:00'), ahora)).toMatchObject({
      clase: 'hecho',
      modificable: false,
    });
  });

  it('rechazado y cancelado no se modifican', () => {
    expect(estadoPlan(plan('rechazado'), ahora)).toMatchObject({ clase: 'rechazado', modificable: false });
    expect(estadoPlan(plan('cancelado'), ahora).modificable).toBe(false);
  });
});
