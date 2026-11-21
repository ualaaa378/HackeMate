import { beforeEach, describe, expect, it } from 'vitest';

import { guardarFiltros, leerFiltros } from './filtrosGuardados';

const PUEBLOS = ['Senés', 'Tahal'];

describe('último filtro de la agenda', () => {
  beforeEach(() => localStorage.clear());

  it('recuerda pueblo y tipo de plan', () => {
    guardarFiltros({ municipio: 'Tahal', categoria: 'fiestas' });
    expect(leerFiltros(PUEBLOS)).toEqual({ municipio: 'Tahal', categoria: 'fiestas' });
  });

  it('ignora valores que ya no existen o guardados rotos', () => {
    localStorage.setItem('hm_filtros_agenda', JSON.stringify({ municipio: 'Madrid', categoria: 'otra' }));
    expect(leerFiltros(PUEBLOS)).toEqual({ municipio: undefined, categoria: undefined });
    localStorage.setItem('hm_filtros_agenda', '{roto');
    expect(leerFiltros(PUEBLOS)).toEqual({});
  });

  it('sin filtros borra lo guardado', () => {
    guardarFiltros({ municipio: 'Senés' });
    guardarFiltros({});
    expect(localStorage.getItem('hm_filtros_agenda')).toBeNull();
  });
});
