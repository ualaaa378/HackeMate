import type { Categoria } from '../api/types';

export function alternarGusto(gustos: Categoria[], c: Categoria): Categoria[] {
  return gustos.includes(c) ? gustos.filter((g) => g !== c) : [...gustos, c];
}
