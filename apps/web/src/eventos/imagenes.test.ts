import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import type { Evento } from '../api/types';
import eventos from '../mocks/eventos.json';

import { FOTOS_PLANES, claveFotoPlan, imagenPlan } from './imagenes';

const plan = (p: Partial<Evento>) => ({ titulo: 'Plan', etiquetas: [], categoria: 'fiestas' as const, ...p });

describe('imágenes de los planes', () => {
  it('elige la foto por etiquetas y título antes que por categoría', () => {
    expect(claveFotoPlan(plan({ titulo: 'Noche de los Burros' }))).toBe('burro');
    expect(claveFotoPlan(plan({ titulo: 'Taller de bachata', etiquetas: ['baile'] }))).toBe('bachata');
    expect(claveFotoPlan(plan({ titulo: 'Taller de sevillanas', etiquetas: ['baile'] }))).toBe('sevillanas');
    expect(claveFotoPlan(plan({ etiquetas: ['fiesta_patronal', 'procesion'] }))).toBe('procesion');
    expect(claveFotoPlan(plan({ titulo: 'Romería Chica a Monteagud', etiquetas: ['romeria'] }))).toBe('romeria');
    expect(claveFotoPlan(plan({ titulo: 'Algo sin pistas', categoria: 'deportiva' }))).toBe('senderismo');
  });

  it('usa la imagen que sube la organización si la hay', () => {
    const img = imagenPlan(plan({ imagen_url: 'data:image/webp;base64,AAAA' }));
    expect(img.src).toBe('data:image/webp;base64,AAAA');
    expect(img.credito).toBeNull();
  });

  it('todos los planes de la demo tienen foto con texto alternativo', () => {
    for (const e of eventos as Evento[]) {
      const img = imagenPlan(e);
      expect(img.alt.length, e.titulo).toBeGreaterThan(20);
    }
  });

  it('los archivos webp existen en public/eventos', () => {
    for (const clave of Object.keys(FOTOS_PLANES)) {
      for (const tam of [320, 900]) {
        expect(existsSync(resolve(__dirname, `../../public/eventos/${clave}-${tam}.webp`)), `${clave}-${tam}`).toBe(
          true,
        );
      }
    }
  });
});
