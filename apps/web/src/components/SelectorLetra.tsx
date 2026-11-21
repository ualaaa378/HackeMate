import { useState } from 'react';

import { letraGuardada, ponerLetra, type TamanoLetra } from '../utils/letra';

const OPCIONES: [TamanoLetra, string][] = [
  ['normal', 'Letra normal'],
  ['grande', 'Letra grande'],
  ['enorme', 'Letra muy grande'],
];

/** Tres botones A A A para agrandar la letra de toda la app. */
const SelectorLetra: React.FC = () => {
  const [actual, setActual] = useState(letraGuardada);
  return (
    <div className="selector-letra" role="group" aria-label="Tamaño de letra">
      <span className="selector-letra__texto">Tamaño de letra</span>
      {OPCIONES.map(([t, etiqueta], i) => (
        <button
          key={t}
          type="button"
          className={`selector-letra__btn selector-letra__btn--${i}`}
          aria-label={etiqueta}
          aria-pressed={actual === t}
          onClick={() => {
            ponerLetra(t);
            setActual(t);
          }}
        >
          A
        </button>
      ))}
    </div>
  );
};

export default SelectorLetra;
