import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonContent,
  IonHeader,
  IonInput,
  IonPage,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';

import { ES_APP_NATIVA, direccionGuardada, guardarDireccion, normalizarDireccion, probarDireccion } from '../servidor';

const Ajustes: React.FC = () => {
  const actual = direccionGuardada();
  const [texto, setTexto] = useState(actual);
  const [estado, setEstado] = useState<'' | 'probando' | 'mal' | 'invalida'>('');

  async function guardar() {
    const direccion = normalizarDireccion(texto);
    if (!direccion) {
      setEstado('invalida');
      return;
    }
    setEstado('probando');
    if (!(await probarDireccion(direccion))) {
      setEstado('mal');
      return;
    }
    guardarDireccion(direccion);
    window.location.reload();
  }

  function quitar() {
    guardarDireccion('');
    window.location.reload();
  }

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <IonBackButton defaultHref="/perfil" text="Volver" />
          </IonButtons>
          <IonTitle>Ajustes</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding contenido-lectura">
        <IonCard>
          <IonCardContent>
            <h2 className="titulo-caja">Dirección del servidor</h2>
            <p>
              Pega aquí la dirección pública de Pueblos Unidos (por ejemplo <code>https://algo.trycloudflare.com</code>
              ). La app la recuerda en este móvil.
            </p>
            <p>
              Ahora:{' '}
              <strong>{actual || (ES_APP_NATIVA ? 'sin configurar (datos de ejemplo)' : 'la de esta web')}</strong>
            </p>
            <IonInput
              label="Dirección"
              labelPlacement="stacked"
              fill="outline"
              type="url"
              inputmode="url"
              autocapitalize="off"
              placeholder="https://…trycloudflare.com"
              value={texto}
              onIonInput={(e) => {
                setTexto(e.detail.value ?? '');
                setEstado('');
              }}
            />
            {estado === 'invalida' && <p role="alert">Eso no parece una dirección web.</p>}
            {estado === 'mal' && (
              <p role="alert">
                No responde Pueblos Unidos en esa dirección. Revisa que esté bien copiada y que el servidor esté
                encendido.
              </p>
            )}
            <IonButton expand="block" onClick={guardar} disabled={estado === 'probando' || !texto.trim()}>
              {estado === 'probando' ? 'Comprobando…' : 'Comprobar y guardar'}
            </IonButton>
            {actual && (
              <IonButton expand="block" fill="clear" onClick={quitar}>
                Quitar la dirección guardada
              </IonButton>
            )}
          </IonCardContent>
        </IonCard>
      </IonContent>
    </IonPage>
  );
};

export default Ajustes;
