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

export function sinHora(e: Evento): boolean {
  return e.etiquetas?.includes('sin_hora') ?? false;
}

export function fechaEstimada(e: Evento): boolean {
  return e.etiquetas?.includes('fecha_estimada') ?? false;
}

/** El plan ya ha terminado. Sin hora de fin, dura hasta el final de su día. */
export function yaPaso(e: Pick<Evento, 'estado' | 'fecha_inicio' | 'fecha_fin'>, ahora = new Date()): boolean {
  if (e.estado === 'finalizado') return true;
  if (e.fecha_fin) return new Date(e.fecha_fin) < ahora;
  return claveDia(e.fecha_inicio) < claveDia(ahora.toISOString());
}

export function horaEvento(e: Evento): string {
  return sinHora(e) ? 'Hora por confirmar' : hora(e.fecha_inicio);
}

export function apuntados(e: Evento): number {
  return e.inscritos ?? 0;
}

export function textoApuntados(e: Evento): string {
  const n = apuntados(e);
  if (n === 0) return 'Aún no se ha apuntado nadie';
  return n === 1 ? '1 persona apuntada' : `${n} personas apuntadas`;
}

export function precio(e: Evento): string {
  if (e.es_gratuito) return 'Gratis';
  if (e.precio_eur == null) return 'Consultar';
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

/** «2026-11-28» + «18:30» → ISO con el desfase de Madrid de ese día (+01:00 en invierno, +02:00 en verano). */
export function isoMadrid(fecha: string, horaTexto: string): string {
  const aprox = new Date(`${fecha}T${horaTexto}:00Z`);
  const enMadrid = new Date(aprox.toLocaleString('en-US', { timeZone: 'Europe/Madrid' }));
  const enUtc = new Date(aprox.toLocaleString('en-US', { timeZone: 'UTC' }));
  const minutos = Math.round((enMadrid.getTime() - enUtc.getTime()) / 60000);
  const signo = minutos >= 0 ? '+' : '-';
  const abs = Math.abs(minutos);
  const hh = String(Math.floor(abs / 60)).padStart(2, '0');
  const mm = String(abs % 60).padStart(2, '0');
  return `${fecha}T${horaTexto}:00${signo}${hh}:${mm}`;
}
