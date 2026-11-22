import { IonChip, IonLabel } from '@ionic/react';

import { CATEGORIAS, type Categoria } from '../api/types';
import { alternarGusto } from '../utils/gustos';

interface Props {
  gustos: Categoria[];
  onCambio: (gustos: Categoria[]) => void;
}

/** N4: gustos opcionales. Sirven para «Para ti» y los avisos de planes nuevos. */
const SelectorGustos: React.FC<Props> = ({ gustos, onCambio }) => (
  <fieldset className="selector-gustos">
    <legend>¿Qué te gusta? (opcional, elige los que quieras)</legend>
    <div className="selector-gustos__chips">
      {(Object.keys(CATEGORIAS) as Categoria[]).map((c) => {
        const marcado = gustos.includes(c);
        return (
          <IonChip
            key={c}
            outline={!marcado}
            color={marcado ? 'primary' : undefined}
            onClick={() => onCambio(alternarGusto(gustos, c))}
            role="checkbox"
            aria-checked={marcado}
          >
            <span aria-hidden="true">{CATEGORIAS[c].emoji}</span>
            <IonLabel>{CATEGORIAS[c].etiqueta}</IonLabel>
          </IonChip>
        );
      })}
    </div>
  </fieldset>
);

export default SelectorGustos;
