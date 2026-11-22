import { CATEGORIAS, type Categoria } from '../api/types';

const CLAVE = 'hm_filtros_agenda';

export interface FiltrosGuardados {
  municipio?: string;
  categoria?: Categoria;
}

/** P1 · último pueblo y tipo de plan elegidos en este dispositivo. Si el navegador no deja guardar, sin filtros. */
export function leerFiltros(municipios: readonly string[]): FiltrosGuardados {
  try {
    const f = JSON.parse(localStorage.getItem(CLAVE) ?? '{}') as Record<string, unknown>;
    return {
      municipio: typeof f.municipio === 'string' && municipios.includes(f.municipio) ? f.municipio : undefined,
      categoria: typeof f.categoria === 'string' && f.categoria in CATEGORIAS ? (f.categoria as Categoria) : undefined,
    };
  } catch {
    return {};
  }
}

export function guardarFiltros(f: FiltrosGuardados): void {
  try {
    if (!f.municipio && !f.categoria) localStorage.removeItem(CLAVE);
    else localStorage.setItem(CLAVE, JSON.stringify(f));
  } catch {
    /* modo privado o almacenamiento bloqueado: no pasa nada, solo no se recuerda */
  }
}
