import { describe, expect, it } from 'vitest';

import { leerEdad } from './edad';

describe('edad (P4b)', () => {
  it('es opcional', () => {
    expect(leerEdad('  ')).toEqual({ edad: null });
  });

  it('acepta de 14 a 120 años', () => {
    expect(leerEdad('14')).toEqual({ edad: 14 });
    expect(leerEdad(' 67 ')).toEqual({ edad: 67 });
    expect(leerEdad('120')).toEqual({ edad: 120 });
  });

  it('explica por qué no vale', () => {
    expect(leerEdad('13')).toHaveProperty('error', expect.stringContaining('14 años'));
    expect(leerEdad('121')).toHaveProperty('error');
    expect(leerEdad('sesenta')).toHaveProperty('error');
    expect(leerEdad('6.5')).toHaveProperty('error');
  });
});
