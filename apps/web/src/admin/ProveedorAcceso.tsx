import { useMemo, useState } from 'react';

import { entrarAdmin, entrarDemo, setAdminDemo } from '../api/admin';
import { ErrorApi, USAR_MOCKS } from '../api/client';
import { useSesion } from '../cuenta/sesion';

import { type AccesoAdmin, ContextoAcceso, type ResultadoAcceso, type RolAdmin } from './acceso';

// Publicador de los mocks: Amigos de Velefique (revisión a mano: sus planes pasan por la bandeja).
const PUBLICADOR_DEMO = { id: '7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01', nombre: 'Amigos de Velefique' };
const CLAVE = 'hm-admin-demo';

function leerDemo(): RolAdmin | null {
  try {
    const v = localStorage.getItem(CLAVE);
    // La moderación sin contraseña solo vale sin API (todo con mocks): con API hay que entrar con usuario y
    // contraseña, aunque en este navegador se entrara antes con el botón de la demo.
    if (v === 'moderador') return USAR_MOCKS ? v : null;
    return v === 'publicador' ? v : null;
  } catch {
    return null;
  }
}

const ProveedorAcceso: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const sesion = useSesion();
  const { usuario } = sesion;
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
    const base = {
      // Primero con la API (POST /auth/demo): así la bandeja, el panel y los planes son los de verdad.
      entrarDemo: async (r: RolAdmin) => {
        const token = await entrarDemo(r);
        if (token) {
          guardar(null);
          sesion.entrar(token);
        } else guardar(r);
      },
      entrarAdmin: async (usuario: string, contrasena: string): Promise<ResultadoAcceso> => {
        if (USAR_MOCKS) {
          // Sin API no hay nada que proteger: la zona del ayuntamiento enseña datos de ejemplo.
          guardar('moderador');
          return 'ok';
        }
        try {
          const token = await entrarAdmin(usuario, contrasena);
          guardar(null);
          sesion.entrar(token);
          return 'ok';
        } catch (e) {
          if (e instanceof ErrorApi && e.code === 'credenciales_invalidas') return 'credenciales';
          if (e instanceof ErrorApi && e.code === 'demasiados_intentos') return 'bloqueado';
          return 'sin_api';
        }
      },
      salir: () => {
        guardar(null);
        if (rolReal) sesion.salir();
      },
    };
    if (rolReal && usuario)
      return {
        ...base,
        rol: rolReal,
        nombre: usuario.nombre,
        publicadorId: rolReal === 'publicador' ? (usuario.publicador_id ?? null) : null,
        demo: false,
      };
    if (rolDemo === 'publicador')
      return { ...base, rol: rolDemo, nombre: PUBLICADOR_DEMO.nombre, publicadorId: PUBLICADOR_DEMO.id, demo: true };
    if (rolDemo === 'moderador')
      return { ...base, rol: rolDemo, nombre: 'Moderación del ayuntamiento', publicadorId: null, demo: true };
    return { ...base, rol: null, nombre: '', publicadorId: null, demo: true };
  }, [rolReal, rolDemo, usuario, sesion]);

  // En el render y no en un efecto: las páginas piden datos en su primer efecto y ya deben saber el modo.
  setAdminDemo(valor.demo);

  return <ContextoAcceso.Provider value={valor}>{children}</ContextoAcceso.Provider>;
};

export default ProveedorAcceso;
