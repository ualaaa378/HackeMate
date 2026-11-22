/** P4a/P4b: en España hace falta tener 14 años para dar el consentimiento de datos (LOPDGDD, art. 7). */
export const EDAD_MINIMA = 14;
export const EDAD_MAXIMA = 120;

/** La edad es opcional: vacío → null. Si está mal, devuelve el mensaje para la persona. */
export function leerEdad(texto: string): { edad: number | null } | { error: string } {
  const t = texto.trim();
  if (!t) return { edad: null };
  if (!/^\d{1,3}$/.test(t)) return { error: 'Escribe la edad en años, solo con números. Por ejemplo: 67.' };
  const edad = Number(t);
  if (edad < EDAD_MINIMA) return { error: `Para crear una cuenta hace falta tener ${EDAD_MINIMA} años o más.` };
  if (edad > EDAD_MAXIMA) return { error: 'Revisa la edad, parece que sobra alguna cifra.' };
  return { edad };
}
