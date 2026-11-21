// Dirección del servidor que usa la app. En la web va incrustada al construir (VITE_API_URL).
// En el APK la web vive en https://localhost, así que la persona pega en Ajustes la URL
// pública del túnel (cambia al reiniciarlo) y se guarda en el dispositivo, sin reinstalar.
import { Capacitor } from '@capacitor/core';

const CLAVE = 'hm-servidor';

export const ES_APP_NATIVA = Capacitor.isNativePlatform();

/** Quita espacios y barras finales; añade https:// si falta. Vacío si no parece una URL. */
export function normalizarDireccion(texto: string): string {
  let v = texto.trim().replace(/\/+$/, '');
  if (!v) return '';
  if (!/^https?:\/\//i.test(v)) v = `https://${v}`;
  try {
    const url = new URL(v);
    return `${url.protocol}//${url.host}${url.pathname.replace(/\/+$/, '')}`;
  } catch {
    return '';
  }
}

export function direccionGuardada(): string {
  try {
    return localStorage.getItem(CLAVE) ?? '';
  } catch {
    return '';
  }
}

export function guardarDireccion(direccion: string): void {
  try {
    if (direccion) localStorage.setItem(CLAVE, direccion);
    else localStorage.removeItem(CLAVE);
  } catch {
    /* sin almacenamiento: no se puede recordar */
  }
}

/** Comprueba que en esa dirección responde la API de HackeMate. */
export async function probarDireccion(direccion: string): Promise<boolean> {
  const control = new AbortController();
  const espera = setTimeout(() => control.abort(), 8000);
  try {
    const resp = await fetch(`${direccion}/api/v1/municipios`, { signal: control.signal });
    return resp.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(espera);
  }
}
