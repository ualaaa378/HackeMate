import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { alCaducarSesion, setToken, USAR_MOCKS } from '../api/client';
import type { Token, Usuario } from '../api/types';

import ModalCuenta from './ModalCuenta';
import { ContextoSesion, type Sesion } from './sesion';

const CLAVE = 'hm-sesion';

function leerGuardada(): Token | null {
  try {
    const t = JSON.parse(localStorage.getItem(CLAVE) ?? 'null') as Token | null;
    // Una sesión de ejemplo (creada cuando no había API) no vale con la API real: con ella, las propuestas
    // se quedaban en el navegador sin llegar al ayuntamiento. Se olvida y se pide entrar de nuevo.
    if (t && t.access_token === 'demo' && !USAR_MOCKS) {
      localStorage.removeItem(CLAVE);
      return null;
    }
    if (t) setToken(t.access_token);
    return t;
  } catch {
    return null;
  }
}

const MOTIVO_GENERAL =
  'Con una cuenta puedes apuntarte a planes y preguntar a la organización. Para mirar la agenda no hace falta.';

const ProveedorSesion: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sesion, setSesion] = useState<Token | null>(leerGuardada);
  const [motivo, setMotivo] = useState<string | null>(null);
  const pendiente = useRef<((u: Usuario) => void) | null>(null);

  const guardar = useCallback((t: Token | null) => {
    setToken(t?.access_token ?? null);
    setSesion(t);
    try {
      if (t) localStorage.setItem(CLAVE, JSON.stringify(t));
      else localStorage.removeItem(CLAVE);
    } catch {
      // sin almacenamiento la sesión dura lo que la pestaña
    }
  }, []);

  useEffect(() => {
    alCaducarSesion(() => guardar(null));
    return () => alCaducarSesion(null);
  }, [guardar]);

  const valor = useMemo<Sesion>(
    () => ({
      usuario: sesion?.usuario ?? null,
      conCuenta: (m, accion) => {
        if (sesion) return accion(sesion.usuario);
        pendiente.current = accion;
        setMotivo(m);
      },
      abrirCuenta: () => {
        pendiente.current = null;
        setMotivo(MOTIVO_GENERAL);
      },
      entrar: (t) => guardar(t),
      actualizarUsuario: (u) => sesion && guardar({ ...sesion, usuario: u }),
      salir: () => guardar(null),
    }),
    [sesion, guardar],
  );

  const alEntrar = (t: Token) => {
    guardar(t);
    setMotivo(null);
    const accion = pendiente.current;
    pendiente.current = null;
    accion?.(t.usuario);
  };

  const alCerrar = () => {
    pendiente.current = null;
    setMotivo(null);
  };

  return (
    <ContextoSesion.Provider value={valor}>
      {children}
      <ModalCuenta abierto={motivo != null} motivo={motivo ?? ''} onEntrar={alEntrar} onCerrar={alCerrar} />
    </ContextoSesion.Provider>
  );
};

export default ProveedorSesion;
