import { IonButton, IonIcon } from '@ionic/react';
import { heart, heartOutline } from 'ionicons/icons';
import { useEffect, useState } from 'react';

import { cambiarMeGusta, getMeGusta, type MeGusta } from '../api/client';
import { useSesion } from '../cuenta/sesion';

/** «Me gusta» de un plan. Cualquiera ve cuántos hay; para darlo hace falta tener cuenta. */
const BotonMeGusta: React.FC<{ eventoId: string }> = ({ eventoId }) => {
  const { usuario, conCuenta } = useSesion();
  const [estado, setEstado] = useState<MeGusta | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let vivo = true;
    getMeGusta(eventoId)
      .then((e) => vivo && setEstado(e))
      .catch(() => vivo && setEstado({ total: 0, mio: false }));
    return () => {
      vivo = false;
    };
  }, [eventoId, usuario?.id]);

  const pulsar = () =>
    conCuenta('Para dar «me gusta» a un plan necesitas una cuenta.', () => {
      const darlo = !estado?.mio;
      setEnviando(true);
      cambiarMeGusta(eventoId, darlo)
        .then(setEstado)
        .catch(() => undefined)
        .finally(() => setEnviando(false));
    });

  const total = estado?.total ?? 0;
  const mio = !!estado?.mio;
  return (
    <IonButton
      className={`boton-me-gusta${mio ? ' boton-me-gusta--mio' : ''}`}
      fill={mio ? 'solid' : 'outline'}
      shape="round"
      size="small"
      disabled={enviando || estado === null}
      aria-pressed={mio}
      onClick={pulsar}
    >
      <IonIcon slot="start" icon={mio ? heart : heartOutline} aria-hidden="true" />
      {mio ? 'Te gusta' : 'Me gusta'}
      <span className="boton-me-gusta__total" aria-label={`, ${total} en total`}>
        {total}
      </span>
    </IonButton>
  );
};

export default BotonMeGusta;
