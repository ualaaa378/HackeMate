// Tamaño de letra elegido por la persona. Se guarda en el dispositivo y se aplica en <html data-letra>.
export type TamanoLetra = 'normal' | 'grande' | 'enorme';
const CLAVE = 'hm-letra';

export function letraGuardada(): TamanoLetra {
  try {
    const v = localStorage.getItem(CLAVE);
    return v === 'grande' || v === 'enorme' ? v : 'normal';
  } catch {
    return 'normal';
  }
}

export function ponerLetra(t: TamanoLetra): void {
  document.documentElement.dataset.letra = t;
  try {
    localStorage.setItem(CLAVE, t);
  } catch {
    /* sin almacenamiento: vale para esta visita */
  }
}
