import { IonBadge, IonItem, IonLabel, IonNote } from '@ionic/react';

import { CATEGORIAS, type Evento } from '../api/types';
import { imagenPlan } from '../eventos/imagenes';
import { apuntados, fechaEstimada, horaEvento, plazas, precio, textoApuntados } from '../utils/formato';

const TarjetaEvento: React.FC<{ evento: Evento; distanciaKm?: number }> = ({ evento: e, distanciaKm }) => {
  const cat = CATEGORIAS[e.categoria];
  const textoPlazas = plazas(e);
  const img = imagenPlan(e);
  return (
    <IonItem routerLink={`/evento/${e.id}`} detail lines="full" className="tarjeta-evento">
      <div slot="start" className="miniatura-plan" aria-hidden="true">
        <img src={img.miniatura} alt="" loading="lazy" decoding="async" />
        <span className="miniatura-plan__emoji" style={{ background: cat.color }}>
          {cat.emoji}
        </span>
      </div>
      <IonLabel>
        <h2>{e.titulo}</h2>
        <p>
          🕘 {horaEvento(e)} · 📍 {e.municipio}
          {distanciaKm != null && ` · a ${distanciaKm.toFixed(1)} km`}
        </p>
        {fechaEstimada(e) && <p>📌 Fecha estimada</p>}
        {textoPlazas && <p>🎟️ {textoPlazas}</p>}
      </IonLabel>
      <IonNote slot="end" className="tarjeta-lateral">
        <IonBadge color={e.es_gratuito ? 'success' : 'medium'}>{precio(e)}</IonBadge>
        <span className="contador-apuntados" title={textoApuntados(e)} aria-label={textoApuntados(e)}>
          👥 {apuntados(e)}
        </span>
      </IonNote>
    </IonItem>
  );
};

export default TarjetaEvento;
