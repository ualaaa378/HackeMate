import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { MUNICIPIOS } from '../api/client';

import { FOTOS_PUEBLOS, fotoDe } from './fotos';

describe('fotos de los pueblos', () => {
  it('cada pueblo de la app tiene foto con texto alternativo y crédito', () => {
    for (const m of MUNICIPIOS) {
      const f = fotoDe(m);
      expect(f, m).toBeDefined();
      expect(f!.alt.length).toBeGreaterThan(20);
      expect(f!.autor).not.toBe('');
      expect(f!.url_original).toMatch(/^https:\/\/commons\.wikimedia\.org\/wiki\/File:/);
    }
  });

  it('los archivos webp existen en public/pueblos', () => {
    for (const f of FOTOS_PUEBLOS) {
      for (const tam of [600, 1200]) {
        expect(existsSync(resolve(__dirname, `../../public/pueblos/${f.base}-${tam}.webp`)), `${f.base}-${tam}`).toBe(
          true,
        );
      }
    }
  });
});
