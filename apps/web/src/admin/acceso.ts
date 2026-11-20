import { createContext, useContext } from 'react';

export type RolAdmin = 'moderador' | 'publicador';
export interface AccesoAdmin {
  rol: RolAdmin | null;
  nombre: string;
  /** Para el publicador: solo ve y crea sus planes. */
  publicadorId: string | null;
  /** true si se ha entrado con el selector de rol de la demo (todo con mocks). */
  demo: boolean;
  entrarDemo: (rol: RolAdmin) => void;
  salir: () => void;
}

export const ContextoAcceso = createContext<AccesoAdmin | null>(null);

export function useAcceso(): AccesoAdmin {
  const a = useContext(ContextoAcceso);
  if (!a) throw new Error('useAcceso fuera de <ProveedorAcceso>');
  return a;
}
