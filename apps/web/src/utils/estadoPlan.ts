import type { Evento } from '../api/types';

import { yaPaso } from './formato';

export interface EstadoPlan {
  texto: string;
  clase: 'revision' | 'publicado' | 'rechazado' | 'hecho' | 'cancelado';
  /** Quien lo propuso aún puede cambiarlo. */
  modificable: boolean;
}

/** Cómo ve su plan quien lo propuso (P5c). Un plan publicado cuya fecha ya pasó cuenta como «ya hecho». */
export function estadoPlan(e: Pick<Evento, 'estado' | 'fecha_inicio' | 'fecha_fin'>, ahora = new Date()): EstadoPlan {
  switch (e.estado) {
    case 'rechazado':
      return { texto: '❌ No publicado', clase: 'rechazado', modificable: false };
    case 'cancelado':
    case 'archivado':
      return { texto: '🚫 Cancelado', clase: 'cancelado', modificable: false };
    case 'finalizado':
      return { texto: '📸 Ya hecho', clase: 'hecho', modificable: false };
    case 'publicado':
      return yaPaso(e, ahora)
        ? { texto: '📸 Ya hecho', clase: 'hecho', modificable: false }
        : { texto: '✅ Publicado', clase: 'publicado', modificable: true };
    default:
      return { texto: '⏳ En revisión', clase: 'revision', modificable: true };
  }
}
