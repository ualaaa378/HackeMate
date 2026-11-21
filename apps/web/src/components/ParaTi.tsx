import { IonList } from '@ionic/react';
import { useEffect, useState } from 'react';

import { getRecomendaciones } from '../api/client';
import type { Recomendacion } from '../api/types';

import TarjetaEvento from './TarjetaEvento';

/** «Para ti» (paso 4 de la demo): lo que la API recomienda a esta persona y por qué. */
const ParaTi: React.FC<{ usuarioId: string; recarga: number }> = ({ usuarioId, recarga }) => {
  const [items, setItems] = useState<Recomendacion[]>([]);

  useEffect(() => {
    let vivo = true;
    getRecomendaciones(usuarioId)
      .then((r) => vivo && setItems(r))
      .catch(() => vivo && setItems([]));
    return () => {
      vivo = false;
    };
  }, [usuarioId, recarga]);

  if (items.length === 0) return null;
  return (
    <section className="para-ti" aria-labelledby="t-para-ti">
      <h2 id="t-para-ti" className="titulo-seccion">
        Para ti
      </h2>
      <IonList lines="none" className="para-ti__lista">
        {items.map((r) => (
          <div key={r.evento.id} className="para-ti__item">
            <TarjetaEvento evento={r.evento} distanciaKm={r.distancia_km ?? undefined} />
            <p className="para-ti__motivo">✨ {r.motivo}</p>
          </div>
        ))}
      </IonList>
    </section>
  );
};

export default ParaTi;
