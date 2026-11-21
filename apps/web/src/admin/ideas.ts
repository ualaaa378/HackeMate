import type { Sugerencias, SugerenciaPlan } from '../api/types';

type ParticipacionPlan = Sugerencias['basado_en'][number];

/** Nombre de cada proveedor de IA para el panel (el bot los llama por su clave). */
export const PROVEEDORES: Record<string, string> = {
  gemini: 'Gemini (principal)',
  nim: 'NVIDIA NIM (respaldo gratis)',
  freellm: 'FreeLLM (respaldo gratis)',
  claude: 'Claude (respaldo)',
  reglas: 'Reglas sin IA (si todo cae)',
};

/** `freellm:llama-3.3-70b` → «FreeLLM (respaldo gratis)». */
export function nombreProveedor(proveedor: string | null | undefined): string {
  if (!proveedor) return 'la IA';
  const clave = proveedor.split(':')[0].trim().toLowerCase();
  return PROVEEDORES[clave] ?? proveedor;
}

/** Una idea se reconoce por título y pueblo: el bot no le pone id y cada consulta se calcula de nuevo. */
export function claveIdea(s: Pick<SugerenciaPlan, 'titulo' | 'municipio'>): string {
  return `${s.titulo.trim().toLowerCase()}|${s.municipio.trim().toLowerCase()}`;
}

/** «Migas solidarias: se ocupó el 90 %, 6 en lista de espera». */
export function textoBasadoEn(p: ParticipacionPlan): string {
  const partes: string[] = [];
  if (p.ocupacion != null) partes.push(`se ocupó el ${Math.round(p.ocupacion * 100)} %`);
  else if (p.inscritos) partes.push(`${p.inscritos} apuntados`);
  if (p.lista_espera) partes.push(`${p.lista_espera} en lista de espera`);
  if (p.preguntas_chat) partes.push(`${p.preguntas_chat} preguntas en el chat`);
  return partes.length ? `${p.titulo}: ${partes.join(', ')}` : p.titulo;
}

const CLAVE_DESCARTADAS = 'hm-ideas-descartadas';

export function leerDescartadas(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(CLAVE_DESCARTADAS) ?? '[]') as string[]);
  } catch {
    return new Set();
  }
}

export function guardarDescartadas(claves: Set<string>): void {
  try {
    localStorage.setItem(CLAVE_DESCARTADAS, JSON.stringify([...claves]));
  } catch {
    // sin almacenamiento, lo descartado vuelve al recargar
  }
}
