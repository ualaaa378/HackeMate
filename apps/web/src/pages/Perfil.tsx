import { IonButton, IonCard, IonCardContent, IonContent, IonHeader, IonPage, IonTitle, IonToolbar } from '@ionic/react';

import { useSesion } from '../cuenta/sesion';

// Bloque 3 (H3.1): gustos, pueblo, tipo de avisos y vincular WhatsApp/Telegram.
const Perfil: React.FC = () => {
  const { usuario, abrirCuenta, salir } = useSesion();
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>👤 Mi perfil</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        {usuario ? (
          <IonCard>
            <IonCardContent>
              <h2 className="titulo-caja">Hola, {usuario.nombre}</h2>
              <p>
                {usuario.telefono
                  ? 'Te avisaremos por WhatsApp de los planes a los que te apuntes.'
                  : 'Has entrado con tu cuenta.'}
              </p>
              <IonButton expand="block" fill="outline" onClick={salir}>
                Cerrar sesión
              </IonButton>
            </IonCardContent>
          </IonCard>
        ) : (
          <IonCard>
            <IonCardContent>
              <h2 className="titulo-caja">Tu cuenta</h2>
              <p>
                Para mirar la agenda y el mapa no hace falta cuenta. La necesitas para apuntarte a un plan o preguntar a
                la organización.
              </p>
              <IonButton expand="block" size="large" onClick={abrirCuenta}>
                Crear cuenta o entrar
              </IonButton>
            </IonCardContent>
          </IonCard>
        )}
      </IonContent>
    </IonPage>
  );
};

export default Perfil;
