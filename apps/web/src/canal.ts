// Canal de mensajería con el que la web habla al vecino (avisos y código de alta).
// Se elige al compilar con VITE_CANAL; el bot y la API ya funcionan con los dos.
export type Canal = 'telegram' | 'whatsapp';

export const CANAL: Canal = import.meta.env.VITE_CANAL === 'whatsapp' ? 'whatsapp' : 'telegram';

export const NOMBRE_CANAL = CANAL === 'whatsapp' ? 'WhatsApp' : 'Telegram';
