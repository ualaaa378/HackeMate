import { createContext, useContext } from 'react';

export type RolAdmin = 'moderador' | 'publicador';
export interface AccesoAdmin {
  rol: RolAdmin | null;
  nombre: string;
  /** Para el publicador: solo ve y crea sus planes. */
  publicadorId: string | null;
  /** true si se trabaja con mocks: no hay API o no deja entrar sin cuenta (DEMO_MODE). */
  demo: boolean;
  /** Entra sin cuenta con el usuario de la demo de ese rol. Con la API en DEMO_MODE, con sesión real. */
  entrarDemo: (rol: RolAdmin) => Promise<void>;
  salir: () => void;
}

export const ContextoAcceso = createContext<AccesoAdmin | null>(null);

export function useAcceso(): AccesoAdmin {
  const a = useContext(ContextoAcceso);
  if (!a) throw new Error('useAcceso fuera de <ProveedorAcceso>');
  return a;
}
