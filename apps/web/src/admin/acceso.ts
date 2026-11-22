import { createContext, useContext } from 'react';

export type RolAdmin = 'moderador' | 'publicador';
/** ok: dentro · credenciales: usuario o contraseña mal · sin_api: no se puede comprobar ahora. */
export type ResultadoAcceso = 'ok' | 'credenciales' | 'bloqueado' | 'sin_api';
export interface AccesoAdmin {
  rol: RolAdmin | null;
  nombre: string;
  /** Para el publicador: solo ve y crea sus planes. */
  publicadorId: string | null;
  /** true si se trabaja con mocks: no hay API o no deja entrar sin cuenta (DEMO_MODE). */
  demo: boolean;
  /** Entra sin cuenta con el usuario de la demo de ese rol (la asociación; la moderación, solo sin API). */
  entrarDemo: (rol: RolAdmin, usuarioId?: string) => Promise<void>;
  /** Moderación del ayuntamiento con usuario y contraseña (POST /auth/admin). */
  entrarAdmin: (usuario: string, contrasena: string) => Promise<ResultadoAcceso>;
  salir: () => void;
}

export const ContextoAcceso = createContext<AccesoAdmin | null>(null);

export function useAcceso(): AccesoAdmin {
  const a = useContext(ContextoAcceso);
  if (!a) throw new Error('useAcceso fuera de <ProveedorAcceso>');
  return a;
}
