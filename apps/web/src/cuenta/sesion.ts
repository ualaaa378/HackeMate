import { createContext, useContext } from 'react';

import type { Usuario } from '../api/types';

export interface Sesion {
  usuario: Usuario | null;
  /**
   * Ejecuta `accion` si hay sesión. Si no, abre la ventana de crear cuenta con `motivo`
   * y la ejecuta al terminar. Mirar la agenda nunca pide cuenta: solo apuntarse y preguntar.
   */
  conCuenta: (motivo: string, accion: (usuario: Usuario) => void) => void;
  abrirCuenta: () => void;
  salir: () => void;
}

export const ContextoSesion = createContext<Sesion | null>(null);

export function useSesion(): Sesion {
  const s = useContext(ContextoSesion);
  if (!s) throw new Error('useSesion fuera de <ProveedorSesion>');
  return s;
}
