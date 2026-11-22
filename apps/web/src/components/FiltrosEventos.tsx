import { IonChip, IonLabel, IonSelect, IonSelectOption } from '@ionic/react';

import { MUNICIPIOS } from '../api/client';
import { CATEGORIAS, type Categoria } from '../api/types';

interface Props {
  municipio?: string;
  categoria?: Categoria;
  onMunicipio: (m?: string) => void;
  onCategoria: (c?: Categoria) => void;
}

const FiltrosEventos: React.FC<Props> = ({ municipio, categoria, onMunicipio, onCategoria }) => (
  <div className="filtros">
    <IonSelect
      label="Pueblo"
      labelPlacement="stacked"
      interface="action-sheet"
      cancelText="Cancelar"
      value={municipio ?? ''}
      onIonChange={(ev) => onMunicipio(ev.detail.value || undefined)}
    >
      <IonSelectOption value="">Todos los pueblos</IonSelectOption>
      {MUNICIPIOS.map((m) => (
        <IonSelectOption key={m} value={m}>
          {m}
        </IonSelectOption>
      ))}
    </IonSelect>
    <div className="chips" role="group" aria-label="Filtrar por categoría">
      {(Object.keys(CATEGORIAS) as Categoria[]).map((c) => (
        <IonChip
          key={c}
          outline={categoria !== c}
          color={categoria === c ? 'primary' : undefined}
          onClick={() => onCategoria(categoria === c ? undefined : c)}
          aria-pressed={categoria === c}
        >
          <span aria-hidden="true">{CATEGORIAS[c].emoji}</span>
          <IonLabel>{CATEGORIAS[c].etiqueta}</IonLabel>
        </IonChip>
      ))}
    </div>
  </div>
);

export default FiltrosEventos;
