import { describe, expect, it } from 'vitest';

import { dniValido } from './dni';

describe('dniValido', () => {
  it('acepta DNI y NIE con la letra de control correcta', () => {
    expect(dniValido('12345678Z')).toBe(true);
    expect(dniValido('12.345.678-z')).toBe(true);
    expect(dniValido('X1234567L')).toBe(true);
  });
  it('rechaza letras mal o formatos raros', () => {
    expect(dniValido('12345678A')).toBe(false);
    expect(dniValido('X1234567A')).toBe(false);
    expect(dniValido('hola')).toBe(false);
  });
});
