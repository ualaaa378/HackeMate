import { IonBackButton, IonButtons, IonContent, IonHeader, IonPage, IonTitle, IonToolbar } from '@ionic/react';

import { FOTOS_PUEBLOS, srcFoto } from '../pueblos/fotos';

const Creditos: React.FC = () => (
  <IonPage>
    <IonHeader>
      <IonToolbar color="secondary">
        <IonButtons slot="start">
          <IonBackButton defaultHref="/agenda" text="Volver" />
        </IonButtons>
        <IonTitle>Créditos de las fotos</IonTitle>
      </IonToolbar>
    </IonHeader>
    <IonContent className="ion-padding">
      <p>
        Las fotos de los pueblos son de Wikimedia Commons y tienen licencia libre. Gracias a quienes las hicieron y las
        compartieron. Las hemos reducido y pasado a formato WebP para que la web cargue rápido.
      </p>
      <ul className="lista-creditos">
        {FOTOS_PUEBLOS.map((f) => (
          <li key={f.base}>
            <img src={srcFoto(f, 600)} alt="" width={600} height={450} loading="lazy" />
            <div>
              <h2>{f.municipio}</h2>
              <p>{f.que}</p>
              <p>
                Autoría: <strong>{f.autor}</strong>
                <br />
                Licencia:{' '}
                <a href={f.url_licencia} target="_blank" rel="noopener noreferrer">
                  {f.licencia}
                </a>
                <br />
                <a href={f.url_original} target="_blank" rel="noopener noreferrer">
                  Ver la foto original en Wikimedia Commons
                </a>
              </p>
            </div>
          </li>
        ))}
      </ul>
    </IonContent>
  </IonPage>
);

export default Creditos;
