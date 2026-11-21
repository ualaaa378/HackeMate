import type { Evento } from '../api/types';

import { claveDia, yaPaso } from './formato';

/** Mes del plan en hora de Madrid, como `AAAA-MM`. */
export function claveMes(iso: string): string {
  return claveDia(iso).slice(0, 7);
}

export function nombreMes(clave: string, ahora = new Date()): string {
  const [ano, mes] = clave.split('-').map(Number);
  const nombre = new Date(Date.UTC(ano, mes - 1, 15)).toLocaleDateString('es-ES', {
    month: 'long',
    timeZone: 'UTC',
  });
  const mayuscula = nombre.charAt(0).toUpperCase() + nombre.slice(1);
  return ano === Number(claveMes(ahora.toISOString()).slice(0, 4)) ? mayuscula : `${mayuscula} ${ano}`;
}

/** Solo los planes que no han terminado: los pasados viven en Recuerdos, no en el mapa. */
export function proximos(eventos: Evento[], ahora = new Date()): Evento[] {
  return eventos.filter((e) => !yaPaso(e, ahora));
}

/** Meses con algún plan próximo, en orden. */
export function mesesConPlanes(eventos: Evento[]): string[] {
  return [...new Set(eventos.map((e) => claveMes(e.fecha_inicio)))].sort();
}

export function delMes(eventos: Evento[], mes?: string): Evento[] {
  return mes ? eventos.filter((e) => claveMes(e.fecha_inicio) === mes) : eventos;
}
