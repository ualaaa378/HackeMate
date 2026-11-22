import type { Evento } from '../api/types';

/** Minúsculas y sin tildes: «senes» encuentra «Senés» y «cabalgata» encuentra «Cabalgata». */
export function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

/** P1 · buscador de la agenda: todas las palabras tienen que salir en el título, la descripción, el lugar o el pueblo. */
export function coincideBusqueda(e: Evento, texto: string): boolean {
  const palabras = normalizar(texto).split(/\s+/).filter(Boolean);
  if (palabras.length === 0) return true;
  const donde = normalizar(
    [e.titulo, e.descripcion, e.lugar, e.municipio, e.publicador_nombre].filter(Boolean).join(' '),
  );
  return palabras.every((p) => donde.includes(p));
}
