import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardSubtitle,
  IonCardTitle,
  IonChip,
  IonContent,
  IonHeader,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonPage,
  IonSpinner,
  IonTitle,
  IonToast,
  IonToolbar,
} from '@ionic/react';
import { calendarOutline, checkmarkCircle, logoFacebook, mapOutline } from 'ionicons/icons';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { getEvento, inscribirse, urlIcs, USAR_MOCKS } from '../api/client';
import { CATEGORIAS, type Evento } from '../api/types';
import { fechaLarga, hora, plazas, precio } from '../utils/formato';

const Ficha: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [evento, setEvento] = useState<Evento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apuntando, setApuntando] = useState(false);
  const [inscrito, setInscrito] = useState<'confirmada' | 'lista_espera' | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getEvento(id)
      .then(setEvento)
      .catch(() => setError('No encontramos este plan.'));
  }, [id]);

  const apuntarme = async () => {
    if (!evento) return;
    setApuntando(true);
    try {
      const insc = await inscribirse(evento.id);
      setInscrito(insc.estado === 'lista_espera' ? 'lista_espera' : 'confirmada');
      setAviso(insc.estado === 'lista_espera' ? 'Estás en la lista de espera' : '¡Plaza confirmada!');
      setEvento(await getEvento(evento.id));
    } catch {
      setAviso('No hemos podido apuntarte. Inténtalo de nuevo.');
    } finally {
      setApuntando(false);
    }
  };

  const enlaceMapa = evento
    ? `https://www.openstreetmap.org/?mlat=${evento.lat}&mlon=${evento.lon}#map=16/${evento.lat}/${evento.lon}`
    : '#';

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="primary">
          <IonButtons slot="start">
            <IonBackButton defaultHref="/agenda" text="Volver" />
          </IonButtons>
          <IonTitle>Plan</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        {!evento && !error && (
          <div className="centrado">
            <IonSpinner aria-label="Cargando" />
          </div>
        )}
        {error && <p>{error}</p>}
        {evento && (
          <>
            <IonCard>
              <IonCardHeader>
                <IonChip style={{ background: CATEGORIAS[evento.categoria].color, color: '#fff' }}>
                  {CATEGORIAS[evento.categoria].emoji} {CATEGORIAS[evento.categoria].etiqueta}
                </IonChip>
                <IonCardTitle>{evento.titulo}</IonCardTitle>
                {evento.publicador_nombre && <IonCardSubtitle>Organiza: {evento.publicador_nombre}</IonCardSubtitle>}
              </IonCardHeader>
              <IonCardContent>
                <IonList lines="none">
                  <IonItem>
                    <IonLabel>
                      📅 {fechaLarga(evento.fecha_inicio)}, a las {hora(evento.fecha_inicio)}
                      {evento.fecha_fin && ` (hasta las ${hora(evento.fecha_fin)})`}
                    </IonLabel>
                  </IonItem>
                  <IonItem>
                    <IonLabel>
                      📍 {evento.lugar ? `${evento.lugar}, ` : ''}
                      {evento.municipio}
                    </IonLabel>
                  </IonItem>
                  <IonItem>
                    <IonLabel>💶 {precio(evento)}</IonLabel>
                  </IonItem>
                  {plazas(evento) && (
                    <IonItem>
                      <IonLabel>🎟️ {plazas(evento)}</IonLabel>
                    </IonItem>
                  )}
                </IonList>
                {evento.descripcion && <p className="descripcion">{evento.descripcion}</p>}
              </IonCardContent>
            </IonCard>

            <IonButton
              expand="block"
              size="large"
              onClick={apuntarme}
              disabled={apuntando || !!inscrito}
              color={inscrito ? 'success' : 'primary'}
            >
              {apuntando ? (
                <IonSpinner name="dots" />
              ) : inscrito ? (
                <>
                  <IonIcon slot="start" icon={checkmarkCircle} aria-hidden="true" />
                  {inscrito === 'confirmada' ? 'Apuntado' : 'En lista de espera'}
                </>
              ) : (
                '🙋 Apuntarme'
              )}
            </IonButton>
            <IonButton
              expand="block"
              fill="outline"
              href={urlIcs(evento.id)}
              disabled={USAR_MOCKS}
              download={`${evento.titulo}.ics`}
            >
              <IonIcon slot="start" icon={calendarOutline} aria-hidden="true" />
              Añadir a mi calendario
            </IonButton>
            <IonButton expand="block" fill="clear" href={enlaceMapa} target="_blank" rel="noopener">
              <IonIcon slot="start" icon={mapOutline} aria-hidden="true" />
              Cómo llegar
            </IonButton>
            {evento.origen.url && (
              <IonButton expand="block" fill="clear" href={evento.origen.url} target="_blank" rel="noopener">
                <IonIcon slot="start" icon={logoFacebook} aria-hidden="true" />
                Ver publicación original
              </IonButton>
            )}
          </>
        )}
        <IonToast isOpen={!!aviso} message={aviso ?? ''} duration={2500} onDidDismiss={() => setAviso(null)} />
      </IonContent>
    </IonPage>
  );
};

export default Ficha;
