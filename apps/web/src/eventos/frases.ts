import type { Categoria, Evento } from '../api/types';

/**
 * Frase de portada que escribe quien publica el plan. Aún no está en el contrato (pendiente de contract-change
 * del flujo A, ver README «Pendiente entre flujos»): se lee solo si la API ya la manda.
 */
export type ConFrase = { frase_portada?: string | null };

// Mientras el bot no tenga su servicio de frases con IA, la web elige una de estas según el tipo de plan.
const FRASES: Record<Categoria, string[]> = {
  cultural: [
    'Una tarde de las que se recuerdan.',
    'Cultura de la buena, a dos pasos de casa.',
    'Trae a tu vecina, que esto no se repite.',
  ],
  fiestas: ['¡Que no falte nadie en la plaza!', 'Música, gente y buen ambiente.', 'Fiesta como las de antes.'],
  gastronomia: ['Ven con hambre, te vas rodando.', 'Sabor de pueblo en cada bocado.', 'Tapa a tapa se hace el camino.'],
  deportiva: ['Zapatillas puestas y a por el monte.', 'Aire puro y piernas a tope.', 'El mejor gimnasio es la sierra.'],
  ludica: ['Diversión para chicos y grandes.', '¡Ponte el disfraz y sal a la calle!', 'Risas garantizadas, palabra.'],
  comercio: ['Lo de aquí, hecho con cariño.', 'Un detalle de tu pueblo para regalar.', 'Compra cerca, vive mejor.'],
};

/** Siempre la misma frase para el mismo plan, para que no cambie al volver a la pantalla. */
export function fraseAutomatica(e: Pick<Evento, 'id' | 'categoria'>): string {
  const lista = FRASES[e.categoria] ?? FRASES.fiestas;
  let h = 0;
  for (const c of e.id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return lista[h % lista.length];
}

export function frasePortada(e: Evento & ConFrase): { texto: string; autor: string } {
  const propia = e.frase_portada?.trim();
  if (propia) return { texto: propia, autor: `— ${e.publicador_nombre || 'La organización'}` };
  return { texto: fraseAutomatica(e), autor: '✨ Frase automática' };
}
