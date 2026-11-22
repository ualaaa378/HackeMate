import { IonButton, IonIcon } from '@ionic/react';
import { calendarOutline, copyOutline } from 'ionicons/icons';
import { useState } from 'react';

import { enModoRespaldo, enlaceGoogleCalendar, urlAgendaIcs } from '../api/client';

/**
 * Conecta la agenda con Google Calendar (u otro calendario) por suscripción: los planes nuevos y los cambios de hora
 * aparecen solos, sin volver a descargar nada. Si hay un pueblo elegido, solo los de ese pueblo.
 */
const SuscribirCalendario: React.FC<{ municipio?: string }> = ({ municipio }) => {
  const [copiado, setCopiado] = useState(false);
  if (enModoRespaldo()) return null;
  const url = urlAgendaIcs(municipio);
  const copiar = () => {
    void navigator.clipboard
      ?.writeText(url)
      .then(() => {
        setCopiado(true);
        window.setTimeout(() => setCopiado(false), 3000);
      })
      .catch(() => window.prompt('Copia este enlace en tu calendario:', url));
  };
  return (
    <section className="suscribir-calendario" aria-labelledby="titulo-suscribir">
      <h2 id="titulo-suscribir" className="suscribir-calendario__titulo">
        📅 Lleva la agenda{municipio ? ` de ${municipio}` : ''} a tu calendario
      </h2>
      <p className="suscribir-calendario__texto">
        Los planes nuevos y los cambios de hora aparecerán solos en tu calendario del móvil. El enlace sirve también
        para Apple u Outlook.
      </p>
      <div className="suscribir-calendario__botones">
        <IonButton href={enlaceGoogleCalendar(url)} target="_blank" rel="noopener" className="boton-google-calendar">
          <IonIcon slot="start" icon={calendarOutline} aria-hidden="true" />
          Añadir a Google Calendar
        </IonButton>
        <IonButton fill="outline" onClick={copiar}>
          <IonIcon slot="start" icon={copyOutline} aria-hidden="true" />
          {copiado ? '¡Enlace copiado!' : 'Copiar enlace'}
        </IonButton>
      </div>
    </section>
  );
};

export default SuscribirCalendario;
