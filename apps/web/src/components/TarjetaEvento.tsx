import { IonBadge, IonItem, IonLabel, IonNote } from '@ionic/react';

import { CATEGORIAS, type Evento } from '../api/types';
import { hora, plazas, precio } from '../utils/formato';

const TarjetaEvento: React.FC<{ evento: Evento; distanciaKm?: number }> = ({ evento: e, distanciaKm }) => {
  const cat = CATEGORIAS[e.categoria];
  const textoPlazas = plazas(e);
  return (
    <IonItem routerLink={`/evento/${e.id}`} detail lines="full" className="tarjeta-evento">
      <div slot="start" className="emoji-categoria" style={{ background: cat.color }} aria-hidden="true">
        {cat.emoji}
      </div>
      <IonLabel>
        <h2>{e.titulo}</h2>
        <p>
          🕘 {hora(e.fecha_inicio)} · 📍 {e.municipio}
          {distanciaKm != null && ` · a ${distanciaKm.toFixed(1)} km`}
        </p>
        {textoPlazas && <p>🎟️ {textoPlazas}</p>}
      </IonLabel>
      <IonNote slot="end">
        <IonBadge color={e.es_gratuito ? 'success' : 'medium'}>{precio(e)}</IonBadge>
      </IonNote>
    </IonItem>
  );
};

export default TarjetaEvento;
