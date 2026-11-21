import { describe, expect, it } from 'vitest';

import { claveIdea, nombreProveedor, textoBasadoEn } from './ideas';

describe('ideas de la IA (N5b)', () => {
  it('nombra el proveedor aunque venga con el modelo', () => {
    expect(nombreProveedor('freellm:llama-3.3-70b')).toBe('FreeLLM (respaldo gratis)');
    expect(nombreProveedor('nim')).toBe('NVIDIA NIM (respaldo gratis)');
    expect(nombreProveedor('otro:x')).toBe('otro:x');
    expect(nombreProveedor(null)).toBe('la IA');
  });

  it('reconoce la misma idea aunque cambien mayúsculas o espacios', () => {
    expect(claveIdea({ titulo: ' Ruta de primavera ', municipio: 'Senés' })).toBe(
      claveIdea({ titulo: 'ruta de primavera', municipio: 'senés' }),
    );
  });

  it('explica en qué plan se basa con sus cifras', () => {
    const base = {
      evento_id: 'x',
      titulo: 'Migas solidarias',
      categoria: 'gastronomia' as const,
      municipio: 'Tahal',
      fecha_inicio: '2026-10-01T12:00:00+02:00',
      inscritos: 4,
      lista_espera: 6,
      preguntas_chat: 0,
    };
    expect(textoBasadoEn({ ...base, ocupacion: 0.9 })).toBe('Migas solidarias: se ocupó el 90 %, 6 en lista de espera');
    expect(textoBasadoEn({ ...base, ocupacion: null, lista_espera: 0 })).toBe('Migas solidarias: 4 apuntados');
  });
});
