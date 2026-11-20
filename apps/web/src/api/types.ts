// Tipos de la API sacados de contracts/openapi.yaml. No se escriben a mano:
// si cambia el contrato, se regenera src/api/openapi.d.ts con `npm run api:tipos`.

import type { components, paths } from './openapi';

type Esquemas = components['schemas'];

export type Evento = Esquemas['evento'];
export type Inscripcion = Esquemas['inscripcion'];
export type Lugar = Esquemas['lugar'];
export type MensajeEvento = Esquemas['mensaje_evento'];
export type Categoria = Esquemas['Categoria'];
export type EstadoEvento = Esquemas['EstadoEvento'];
export type Canal = Evento['origen']['canal'];
export type ApiError = Esquemas['Error'];

export interface Pagina<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export type FiltrosEventos = NonNullable<paths['/api/v1/eventos']['get']['parameters']['query']>;

export const CATEGORIAS: Record<Categoria, { etiqueta: string; emoji: string; color: string }> = {
  deportiva: { etiqueta: 'Deportiva', emoji: '🥾', color: '#2e7d32' },
  cultural: { etiqueta: 'Cultural', emoji: '🎭', color: '#6a1b9a' },
  fiestas: { etiqueta: 'Fiestas', emoji: '🎉', color: '#c62828' },
  gastronomia: { etiqueta: 'Gastronomía', emoji: '🍽️', color: '#ef6c00' },
  ludica: { etiqueta: 'Lúdica', emoji: '🎲', color: '#1565c0' },
  comercio: { etiqueta: 'Comercio', emoji: '🛍️', color: '#00838f' },
};
