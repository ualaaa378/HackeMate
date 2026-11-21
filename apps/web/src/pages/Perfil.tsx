import {
  IonButton,
  IonCard,
  IonCardContent,
  IonContent,
  IonHeader,
  IonPage,
  IonRouterLink,
  IonTitle,
  IonToolbar,
} from '@ionic/react';

import { NOMBRE_CANAL } from '../canal';
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
                  ? `Te avisaremos por ${NOMBRE_CANAL} de los planes a los que te apuntes.`
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
        <IonCard>
          <IonCardContent>
            <h2 className="titulo-caja">¿Tienes una idea para tu pueblo?</h2>
            <p>Propón un plan: el ayuntamiento lo revisa y, si lo aprueba, sale en la agenda.</p>
            <IonButton expand="block" fill="outline" routerLink="/proponer">
              Proponer un plan
            </IonButton>
          </IonCardContent>
        </IonCard>
        <IonCard>
          <IonCardContent>
            <h2 className="titulo-caja">¿Eres del ayuntamiento o de una asociación?</h2>
            <p>Revisa los planes que llegan, publica los tuyos y mira las cifras de la agenda.</p>
            <IonButton expand="block" fill="outline" routerLink="/admin">
              🏛️ Entrar en la zona del ayuntamiento
            </IonButton>
          </IonCardContent>
        </IonCard>
        <p className="enlace-creditos">
          <IonRouterLink routerLink="/creditos">Créditos de las fotos de los pueblos</IonRouterLink>
        </p>
      </IonContent>
    </IonPage>
  );
};

export default Perfil;
