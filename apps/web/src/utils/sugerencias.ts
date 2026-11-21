import { CATEGORIAS, type Categoria, type Evento } from '../api/types';

export interface Sugerido {
  evento: Evento;
  motivo: string;
}

/**
 * Sugerencias hechas en el dispositivo, para cuando la API no recomienda nada (sin sesión o sin datos):
 * planes de las categorías que le gustan y parecidos (misma categoría o mismo pueblo) a los que ya se apuntó.
 */
export function sugerirParecidos(
  proximos: Evento[],
  mios: Set<string>,
  gustos: Categoria[] = [],
  maximo = 4,
): Sugerido[] {
  const apuntados = proximos.filter((e) => mios.has(e.id));
  // El mismo plan puede venir dos veces (p. ej. importado de dos fuentes): no se sugiere lo que ya tiene.
  const titulos = new Set(apuntados.map((a) => a.titulo.trim().toLowerCase()));
  const puntuados = proximos
    .filter((e) => !mios.has(e.id) && !titulos.has(e.titulo.trim().toLowerCase()))
    .map((e) => {
      const mismaCategoria = apuntados.find((a) => a.categoria === e.categoria);
      const mismoPueblo = apuntados.find((a) => a.municipio === e.municipio);
      const leGusta = gustos.includes(e.categoria);
      const puntos = (leGusta ? 2 : 0) + (mismaCategoria ? 2 : 0) + (mismoPueblo ? 1 : 0);
      const motivo = mismaCategoria
        ? `Parecido a «${mismaCategoria.titulo}», al que te apuntaste`
        : leGusta
          ? `Te gustan los planes de ${CATEGORIAS[e.categoria].etiqueta.toLowerCase()}`
          : mismoPueblo
            ? `En ${e.municipio}, como «${mismoPueblo.titulo}»`
            : '';
      return { evento: e, motivo, puntos };
    })
    .filter((s) => s.puntos > 0)
    .sort((a, b) => b.puntos - a.puntos || a.evento.fecha_inicio.localeCompare(b.evento.fecha_inicio));
  return puntuados.slice(0, maximo).map(({ evento, motivo }) => ({ evento, motivo }));
}
