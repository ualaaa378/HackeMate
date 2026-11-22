import { CANAL } from '../canal';

/** Enlace de Google Maps con la ruta hasta el plan desde donde esté la persona. */
export function enlaceComoLlegar(lat: number, lon: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;
}

/** Enlace para mandar el plan por el canal de mensajería configurado (VITE_CANAL). */
export function enlaceEnviarPorCanal(texto: string, url: string): string {
  return CANAL === 'whatsapp'
    ? `https://wa.me/?text=${encodeURIComponent(`${texto} ${url}`)}`
    : `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(texto)}`;
}
