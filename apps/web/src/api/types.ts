// Tipos alineados con contracts/schemas/evento.json.
// Cuando exista contracts/openapi.yaml, se sustituyen por los generados con openapi-typescript.

export type Categoria = 'deportiva' | 'cultural' | 'fiestas' | 'gastronomia' | 'ludica' | 'comercio';

export type EstadoEvento =
  | 'borrador'
  | 'pendiente_confirmacion'
  | 'en_revision'
  | 'publicado'
  | 'rechazado'
  | 'cancelado'
  | 'finalizado'
  | 'archivado';

export type Canal = 'whatsapp' | 'web' | 'panel' | 'facebook' | 'instagram' | 'web_externa' | 'manual';

export interface Evento {
  id: string;
  titulo: string;
  descripcion?: string;
  categoria: Categoria;
  etiquetas?: string[];
  municipio: string;
  lugar?: string | null;
  lat: number;
  lon: number;
  fecha_inicio: string;
  fecha_fin?: string | null;
  precio_eur?: number | null;
  es_gratuito: boolean;
  plazas_totales?: number | null;
  plazas_libres?: number | null;
  inscritos?: number;
  estado: EstadoEvento;
  publicador_id?: string | null;
  publicador_nombre?: string | null;
  imagen_url?: string | null;
  origen: { canal: Canal; url?: string | null; importado_auto: boolean };
  moderacion?: { motivo?: string | null; score_spam?: number | null; revisado_por?: string | null };
  creado_en?: string;
  actualizado_en?: string;
}

export interface Pagina<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface FiltrosEventos {
  municipio?: string;
  categoria?: Categoria;
  desde?: string;
  hasta?: string;
  lat?: number;
  lon?: number;
  radio_km?: number;
  page?: number;
  size?: number;
}

export interface Inscripcion {
  id: string;
  evento_id: string;
  estado: 'confirmada' | 'lista_espera' | 'cancelada' | 'asistio' | 'no_asistio';
}

export interface ApiError {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export const CATEGORIAS: Record<Categoria, { etiqueta: string; emoji: string; color: string }> = {
  deportiva: { etiqueta: 'Deportiva', emoji: '🥾', color: '#2e7d32' },
  cultural: { etiqueta: 'Cultural', emoji: '🎭', color: '#6a1b9a' },
  fiestas: { etiqueta: 'Fiestas', emoji: '🎉', color: '#c62828' },
  gastronomia: { etiqueta: 'Gastronomía', emoji: '🍽️', color: '#ef6c00' },
  ludica: { etiqueta: 'Lúdica', emoji: '🎲', color: '#1565c0' },
  comercio: { etiqueta: 'Comercio', emoji: '🛍️', color: '#00838f' },
};
