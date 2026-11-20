import type { Evento } from '../api/types';

const ZONA = 'Europe/Madrid';

export function fechaLarga(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: ZONA,
  });
}

export function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', timeZone: ZONA });
}

export function claveDia(iso: string): string {
  return new Date(iso).toLocaleDateString('sv-SE', { timeZone: ZONA });
}

export function precio(e: Evento): string {
  if (e.es_gratuito || e.precio_eur == null) return 'Gratis';
  return `${e.precio_eur.toLocaleString('es-ES', { maximumFractionDigits: 2 })} €`;
}

export function plazas(e: Evento): string | null {
  if (e.plazas_totales == null) return null;
  if (!e.plazas_libres) return 'Completo · lista de espera';
  return `${e.plazas_libres} de ${e.plazas_totales} plazas libres`;
}

export function agruparPorDia(eventos: Evento[]): [string, Evento[]][] {
  const grupos = new Map<string, Evento[]>();
  for (const e of eventos) {
    const k = claveDia(e.fecha_inicio);
    grupos.set(k, [...(grupos.get(k) ?? []), e]);
  }
  return [...grupos.entries()].sort(([a], [b]) => a.localeCompare(b));
}
