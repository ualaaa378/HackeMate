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
export type Usuario = Esquemas['usuario'];
export type Token = Esquemas['Token'];
export type UsuarioEditar = Esquemas['UsuarioEditar'];
export type MensajeCrear = Esquemas['MensajeCrear'];
export type EventoCrear = Esquemas['EventoCrear'];

export const PUBLICOS = {
  todos: 'Todos los públicos',
  infantil: 'Infantil y familias',
  adultos: 'Solo mayores de 18',
  mayores: 'Personas mayores',
} as const;
export type Publico = keyof typeof PUBLICOS;

export const NECESIDADES = {
  espacio: 'Usar un espacio municipal (plaza, salón, pabellón…)',
  calle: 'Cortar una calle o el tráfico',
  material: 'Mesas, sillas o escenario',
  luz: 'Toma de luz o equipo de sonido',
  musica: 'Música amplificada o fuegos',
  comida: 'Vender o servir comida y bebida',
  seguridad: 'Protección Civil, Policía o ambulancia',
  limpieza: 'Limpieza y contenedores después',
  difusion: 'Ayuda para anunciarlo (bando, redes, cartel)',
} as const;
export type Necesidad = keyof typeof NECESIDADES;

/**
 * Datos de la propuesta que solo ve el ayuntamiento. Aún NO están en el contrato:
 * hasta que se añadan (contract-change), la API solo recibe la parte pública (EventoCrear).
 */
export interface DatosAyuntamiento {
  responsable: string;
  telefono: string;
  entidad: 'particular' | 'asociacion' | 'comercio' | 'otra';
  entidad_nombre?: string;
  publico: Publico;
  necesidades: Necesidad[];
  seguro_rc: 'si' | 'no' | 'nose';
  observaciones?: string;
}
export type Publicador = Esquemas['publicador'];
export type Pendiente = Esquemas['Pendiente'];
/** Elemento de la bandeja. `propuesta` son los datos privados de un plan vecinal (aún fuera del contrato). */
export type PendienteBandeja = Pendiente & { propuesta?: DatosAyuntamiento };
export type Decision = Esquemas['Decision'];
export type Estadisticas = Esquemas['Estadisticas'];
export type EventoEditar = Esquemas['EventoEditar'];
export type Rol = Usuario['rol'];

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
