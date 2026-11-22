// Canal de mensajería con el que la web habla al vecino (avisos y código de alta).
// Se elige al compilar con VITE_CANAL; el bot y la API ya funcionan con los dos.
export type Canal = 'telegram' | 'whatsapp';

export const CANAL: Canal = import.meta.env.VITE_CANAL === 'whatsapp' ? 'whatsapp' : 'telegram';

export const NOMBRE_CANAL = CANAL === 'whatsapp' ? 'WhatsApp' : 'Telegram';

// Contacto del bot que se enseña en Perfil para usarlo solo con audios. Opcional: VITE_CANAL_CONTACTO.
export const CONTACTO_CANAL: string =
  (import.meta.env.VITE_CANAL_CONTACTO as string | undefined) || (CANAL === 'telegram' ? '@HackeMate_bot' : '');

export const ENLACE_CANAL: string | null =
  CANAL === 'telegram' && CONTACTO_CANAL.startsWith('@') ? `https://t.me/${CONTACTO_CANAL.slice(1)}` : null;
