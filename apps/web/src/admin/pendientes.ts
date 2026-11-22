import { useEffect, useState } from 'react';

import { getPendientes } from '../api/admin';

/** La bandeja lo lanza al aprobar o rechazar, para que el número de la pestaña baje al momento. */
export const EVENTO_BANDEJA = 'hm-bandeja-cambio';

const CADA_MS = 30_000;

/** Cuántos planes esperan en la bandeja. null mientras no se sabe o si no hay que mirarlo. */
export function usePendientesBandeja(activo: boolean, recargar: unknown): number | null {
  const [n, setN] = useState<number | null>(null);
  useEffect(() => {
    if (!activo) return;
    let vivo = true;
    const leer = () =>
      void getPendientes()
        .then((p) => vivo && setN(p.total ?? p.items.length))
        .catch(() => vivo && setN(null));
    leer();
    const reloj = window.setInterval(leer, CADA_MS);
    window.addEventListener(EVENTO_BANDEJA, leer);
    return () => {
      vivo = false;
      window.clearInterval(reloj);
      window.removeEventListener(EVENTO_BANDEJA, leer);
    };
  }, [activo, recargar]);
  return activo ? n : null;
}
