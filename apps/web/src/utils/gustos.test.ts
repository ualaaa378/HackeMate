import { describe, expect, it } from 'vitest';

import { alternarGusto } from './gustos';

describe('alternarGusto', () => {
  it('añade un gusto que no estaba y quita uno que ya estaba', () => {
    expect(alternarGusto(['cultural'], 'fiestas')).toEqual(['cultural', 'fiestas']);
    expect(alternarGusto(['cultural', 'fiestas'], 'cultural')).toEqual(['fiestas']);
  });
});
