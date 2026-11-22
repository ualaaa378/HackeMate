import { useSyncExternalStore } from 'react';

/** Ancho a partir del cual la agenda se reparte en tres zonas (N1). En móvil y en la APK no cambia nada. */
export const CONSULTA_PANTALLA_GRANDE = '(min-width: 1100px)';

function suscribir(aviso: () => void): () => void {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {};
  const m = window.matchMedia(CONSULTA_PANTALLA_GRANDE);
  m.addEventListener('change', aviso);
  return () => m.removeEventListener('change', aviso);
}

function leer(): boolean {
  return typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(CONSULTA_PANTALLA_GRANDE).matches;
}

export function usePantallaGrande(): boolean {
  return useSyncExternalStore(suscribir, leer, () => false);
}
