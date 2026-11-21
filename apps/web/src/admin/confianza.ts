// Reglas para que una asociación publique sin revisión. Solo hay dos modos:
// a mano (el moderador revisa cada plan) o automática (sale directo, salvo que el antispam lo pare).
// En el contrato, «automática» es nivel_confianza 2 y «a mano» es 0 (el 1 está obsoleto y la API lo trata como 0).

import type { PublicadorAdmin } from '../api/types';

export const REGLAS = {
  /** Planes aprobados que necesita en la ventana de días para pasar a automática. */
  planesMinimos: 3,
  ventanaDias: 60,
  /** Sin publicar en estos días, vuelve a revisión a mano. */
  diasInactividad: 90,
};

export type ModoRevision = 'manual' | 'automatica';

export function modoRevision(p: Pick<PublicadorAdmin, 'nivel_confianza'>): ModoRevision {
  return p.nivel_confianza === 2 ? 'automatica' : 'manual';
}

export interface Requisito {
  texto: string;
  cumple: boolean;
}

function diasDesde(iso: string | null | undefined, hoy: Date): number {
  if (!iso) return Infinity;
  return (hoy.getTime() - new Date(iso).getTime()) / 86_400_000;
}

export function requisitos(p: PublicadorAdmin, hoy = new Date()): Requisito[] {
  const r = p.responsable;
  const a = p.actividad ?? { planes_60_dias: 0, rechazados_60_dias: 0, ultimo_plan: null };
  const tieneDatos = Boolean(r?.dni && r.residencia);
  return [
    {
      texto: !tieneDatos
        ? 'Falta que el responsable aporte su DNI y dónde vive'
        : r!.identidad_verificada
          ? 'Responsable identificado: DNI y residencia comprobados'
          : 'El responsable ha aportado DNI y residencia, falta comprobarlos',
      cumple: tieneDatos && r!.identidad_verificada,
    },
    {
      texto: `Publica a menudo: ${a.planes_60_dias} ${a.planes_60_dias === 1 ? 'plan aprobado' : 'planes aprobados'} en los últimos ${REGLAS.ventanaDias} días (mínimo ${REGLAS.planesMinimos})`,
      cumple: a.planes_60_dias >= REGLAS.planesMinimos,
    },
    {
      texto:
        a.rechazados_60_dias === 0
          ? `Ningún plan rechazado en los últimos ${REGLAS.ventanaDias} días`
          : `${a.rechazados_60_dias} ${a.rechazados_60_dias === 1 ? 'plan rechazado' : 'planes rechazados'} en los últimos ${REGLAS.ventanaDias} días`,
      cumple: a.rechazados_60_dias === 0,
    },
    {
      texto:
        diasDesde(a.ultimo_plan, hoy) <= REGLAS.diasInactividad
          ? `Sigue activa: ha publicado en los últimos ${REGLAS.diasInactividad} días`
          : `Lleva más de ${REGLAS.diasInactividad} días sin publicar`,
      cumple: diasDesde(a.ultimo_plan, hoy) <= REGLAS.diasInactividad,
    },
  ];
}

export function puedeSerAutomatica(p: PublicadorAdmin, hoy = new Date()): boolean {
  return requisitos(p, hoy).every((x) => x.cumple);
}

/** Está en automática pero ha dejado de cumplir algo: el moderador debería pasarla a mano. */
export function deberiaVolverAManual(p: PublicadorAdmin, hoy = new Date()): boolean {
  return modoRevision(p) === 'automatica' && !puedeSerAutomatica(p, hoy);
}

/** «45871236J» → «•••••236J». El DNI completo no se enseña nunca en pantalla. */
export function dniOculto(dni: string): string {
  return dni.length > 4 ? '•'.repeat(dni.length - 4) + dni.slice(-4) : dni;
}
