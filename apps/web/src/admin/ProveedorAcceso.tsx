import { useMemo, useState } from 'react';

import { setAdminDemo } from '../api/admin';
import { useSesion } from '../cuenta/sesion';

import { type AccesoAdmin, ContextoAcceso, type RolAdmin } from './acceso';

// Publicador de la demo: Amigos de Velefique (nivel 1, sus planes pasan por la bandeja).
const PUBLICADOR_DEMO = { id: '7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01', nombre: 'Amigos de Velefique' };
const CLAVE = 'hm-admin-demo';

function leerDemo(): RolAdmin | null {
  try {
    const v = localStorage.getItem(CLAVE);
    return v === 'moderador' || v === 'publicador' ? v : null;
  } catch {
    return null;
  }
}

const ProveedorAcceso: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { usuario } = useSesion();
  const [rolDemo, setRolDemo] = useState<RolAdmin | null>(leerDemo);

  const rolReal = usuario?.rol === 'moderador' || usuario?.rol === 'publicador' ? usuario.rol : null;

  const valor = useMemo<AccesoAdmin>(() => {
    const guardar = (r: RolAdmin | null) => {
      setRolDemo(r);
      try {
        if (r) localStorage.setItem(CLAVE, r);
        else localStorage.removeItem(CLAVE);
      } catch {
        // sin almacenamiento dura lo que la pestaña
      }
    };
    const base = { entrarDemo: (r: RolAdmin) => guardar(r), salir: () => guardar(null) };
    if (rolReal && usuario) return { ...base, rol: rolReal, nombre: usuario.nombre, publicadorId: null, demo: false };
    if (rolDemo === 'publicador')
      return { ...base, rol: rolDemo, nombre: PUBLICADOR_DEMO.nombre, publicadorId: PUBLICADOR_DEMO.id, demo: true };
    if (rolDemo === 'moderador')
      return { ...base, rol: rolDemo, nombre: 'Moderación del ayuntamiento', publicadorId: null, demo: true };
    return { ...base, rol: null, nombre: '', publicadorId: null, demo: true };
  }, [rolReal, rolDemo, usuario]);

  // En el render y no en un efecto: las páginas piden datos en su primer efecto y ya deben saber el modo.
  setAdminDemo(valor.demo);

  return <ContextoAcceso.Provider value={valor}>{children}</ContextoAcceso.Provider>;
};

export default ProveedorAcceso;
