import { describe, expect, it } from 'vitest';

import type { Evento } from '../api/types';

import { delMes, mesesConPlanes, nombreMes, proximos } from './meses';

const ev = (id: string, fecha_inicio: string, extra: Partial<Evento> = {}) =>
  ({ id, fecha_inicio, estado: 'publicado', ...extra }) as Evento;

const ahora = new Date('2026-11-21T18:00:00+01:00');
const lista = [
  ev('pasado', '2026-11-10T10:00:00+01:00'),
  ev('finalizado', '2026-11-25T10:00:00+01:00', { estado: 'finalizado' }),
  ev('hoy', '2026-11-21T10:00:00+01:00'),
  ev('dic', '2026-12-05T10:00:00+01:00'),
  ev('ene', '2027-01-06T10:00:00+01:00'),
];

describe('meses del mapa', () => {
  it('quita los planes pasados y los finalizados', () => {
    expect(proximos(lista, ahora).map((e) => e.id)).toEqual(['hoy', 'dic', 'ene']);
  });

  it('lista los meses con planes, en orden', () => {
    expect(mesesConPlanes(proximos(lista, ahora))).toEqual(['2026-11', '2026-12', '2027-01']);
  });

  it('filtra por mes y sin mes devuelve todos', () => {
    const p = proximos(lista, ahora);
    expect(delMes(p, '2026-12').map((e) => e.id)).toEqual(['dic']);
    expect(delMes(p)).toHaveLength(3);
  });

  it('nombra el mes y añade el año si no es el actual', () => {
    expect(nombreMes('2026-12', ahora)).toBe('Diciembre');
    expect(nombreMes('2027-01', ahora)).toBe('Enero 2027');
  });
});
