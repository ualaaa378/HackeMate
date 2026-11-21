import { IonIcon, IonItem } from '@ionic/react';
import { locationOutline, peopleOutline, timeOutline } from 'ionicons/icons';

import { CATEGORIAS, type Evento } from '../api/types';
import { imagenPlan } from '../eventos/imagenes';
import { apuntados, fechaEstimada, horaEvento, plazas, precio, textoApuntados } from '../utils/formato';

const TarjetaEvento: React.FC<{ evento: Evento; distanciaKm?: number }> = ({ evento: e, distanciaKm }) => {
  const cat = CATEGORIAS[e.categoria];
  const textoPlazas = plazas(e);
  const img = imagenPlan(e);
  const n = apuntados(e);
  return (
    <IonItem routerLink={`/evento/${e.id}`} detail={false} lines="none" className="tarjeta-evento">
      <div className="tarjeta-evento__cuerpo">
        <div className="miniatura-plan" aria-hidden="true">
          <img src={img.miniatura} alt="" loading="lazy" decoding="async" />
          <span className="miniatura-plan__emoji" style={{ background: cat.color }}>
            {cat.emoji}
          </span>
        </div>
        <div className="tarjeta-evento__texto">
          <h2>{e.titulo}</h2>
          <p className="tarjeta-evento__meta">
            <span>
              <IonIcon icon={timeOutline} aria-hidden="true" />
              {horaEvento(e)}
            </span>
            <span>
              <IonIcon icon={locationOutline} aria-hidden="true" />
              {e.municipio}
              {distanciaKm != null && `, a ${distanciaKm.toFixed(1)} km`}
            </span>
          </p>
          <p className="tarjeta-evento__chapas">
            <span className={`chapa ${e.es_gratuito ? 'chapa--gratis' : 'chapa--precio'}`}>
              {e.es_gratuito || e.precio_eur != null ? precio(e) : 'Precio a consultar'}
            </span>
            {n > 0 && (
              <span className="chapa chapa--gente" aria-label={textoApuntados(e)}>
                <IonIcon icon={peopleOutline} aria-hidden="true" />
                {n}
              </span>
            )}
            {textoPlazas && <span className="chapa chapa--aviso">{textoPlazas}</span>}
            {fechaEstimada(e) && <span className="chapa chapa--aviso">Fecha estimada</span>}
          </p>
        </div>
      </div>
    </IonItem>
  );
};

export default TarjetaEvento;
