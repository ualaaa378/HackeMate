/** Misma regla que la API (services/api/app/confianza.py): la letra de control del DNI o NIE. */
export function dniValido(dni: string): boolean {
  const limpio = dni.replace(/[\s.-]/g, '').toUpperCase();
  const m = /^(\d{8})([A-Z])$/.exec(limpio) ?? /^([XYZ])(\d{7})([A-Z])$/.exec(limpio);
  if (!m) return false;
  const numero = m.length === 3 ? Number(m[1]) : 'XYZ'.indexOf(m[1]) * 10_000_000 + Number(m[2]);
  return 'TRWAGMYFPDXBNJZSQVHLCKE'[numero % 23] === m[m.length - 1];
}
