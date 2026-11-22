import { describe, expect, it } from 'vitest';

import type { Evento } from '../api/types';

import { coincideBusqueda, normalizar } from './busqueda';

const plan = {
  titulo: 'Cabalgata de Reyes Magos',
  descripcion: 'Desfile por las calles con caramelos',
  lugar: 'Plaza de la Iglesia',
  municipio: 'Senés',
} as Evento;

describe('buscador de la agenda', () => {
  it('quita tildes y mayúsculas', () => {
    expect(normalizar('  Senés ')).toBe('senes');
  });

  it('encuentra por título, descripción, lugar o pueblo sin tildes', () => {
    expect(coincideBusqueda(plan, 'cabalgata')).toBe(true);
    expect(coincideBusqueda(plan, 'caramelos')).toBe(true);
    expect(coincideBusqueda(plan, 'iglesia')).toBe(true);
    expect(coincideBusqueda(plan, 'senes')).toBe(true);
  });

  it('pide todas las palabras y deja pasar todo si está vacío', () => {
    expect(coincideBusqueda(plan, 'reyes senes')).toBe(true);
    expect(coincideBusqueda(plan, 'reyes tahal')).toBe(false);
    expect(coincideBusqueda(plan, '   ')).toBe(true);
  });
});
