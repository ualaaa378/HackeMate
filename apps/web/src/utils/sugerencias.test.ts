import { describe, expect, it } from 'vitest';

import type { Evento } from '../api/types';

import { sugerirParecidos } from './sugerencias';

const ev = (id: string, categoria: Evento['categoria'], municipio: string, dia: number) =>
  ({
    id,
    titulo: id,
    categoria,
    municipio,
    fecha_inicio: `2026-12-${String(dia).padStart(2, '0')}T10:00:00+01:00`,
  }) as Evento;

const lista = [
  ev('ruta', 'deportiva', 'Senés', 1),
  ev('otra-ruta', 'deportiva', 'Tahal', 5),
  ev('teatro', 'cultural', 'Velefique', 3),
  ev('mercado', 'comercio', 'Senés', 2),
  ev('fiesta', 'fiestas', 'Tahal', 4),
];

describe('sugerirParecidos', () => {
  it('sin plan ni gustos no sugiere nada', () => {
    expect(sugerirParecidos(lista, new Set())).toEqual([]);
  });

  it('sugiere planes parecidos a los suyos y nunca uno al que ya va', () => {
    const r = sugerirParecidos(lista, new Set(['ruta']));
    expect(r.map((s) => s.evento.id)).toEqual(['otra-ruta', 'mercado']);
    expect(r[0].motivo).toBe('Parecido a «ruta», al que te apuntaste');
    expect(r[1].motivo).toBe('En Senés, como «ruta»');
  });

  it('no sugiere el mismo plan repetido con otro id', () => {
    const r = sugerirParecidos([...lista, { ...lista[0], id: 'ruta-copia' }], new Set(['ruta']));
    expect(r.map((s) => s.evento.id)).not.toContain('ruta-copia');
  });

  it('pone primero lo que le gusta y lo parecido, y respeta el máximo', () => {
    const r = sugerirParecidos(lista, new Set(['ruta']), ['cultural'], 2);
    expect(r.map((s) => s.evento.id)).toEqual(['teatro', 'otra-ruta']);
    expect(r[0].motivo).toBe('Te gustan los planes de cultural');
  });
});
