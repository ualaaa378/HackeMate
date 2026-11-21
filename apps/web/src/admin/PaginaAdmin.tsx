import {
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonContent,
  IonHeader,
  IonPage,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { Navigate } from 'react-router-dom';

import SelectorLetra from '../components/SelectorLetra';
import { useSesion } from '../cuenta/sesion';

import { type RolAdmin, useAcceso } from './acceso';

/** Marco de todas las pantallas de /admin. Sin rol de moderador o publicador enseña la puerta de entrada. */
const PaginaAdmin: React.FC<{
  titulo: string;
  roles?: RolAdmin[];
  acciones?: React.ReactNode;
  children: React.ReactNode;
}> = ({ titulo, roles = ['moderador', 'publicador'], acciones, children }) => {
  const acceso = useAcceso();
  const permitido = acceso.rol != null && roles.includes(acceso.rol);
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>{titulo}</IonTitle>
          <IonButtons slot="end">{permitido && acciones}</IonButtons>
        </IonToolbar>
        {acceso.rol && (
          <div className="franja-admin" role="note">
            <span>
              {acceso.rol === 'moderador' ? '🏛️' : '🤝'} {acceso.nombre}
              {acceso.demo && ' · modo demo'}
            </span>
            <IonButton size="small" fill="clear" routerLink="/agenda" onClick={acceso.salir}>
              Salir
            </IonButton>
          </div>
        )}
      </IonHeader>
      <IonContent className="ion-padding contenido-admin">
        <SelectorLetra />
        {permitido ? children : <Puerta rolActual={acceso.rol} />}
      </IonContent>
    </IonPage>
  );
};

const Puerta: React.FC<{ rolActual: RolAdmin | null }> = ({ rolActual }) => {
  const { entrarDemo } = useAcceso();
  const { abrirCuenta } = useSesion();
  return (
    <IonCard className="puerta-admin">
      <IonCardContent>
        {rolActual ? (
          // La asociación solo tiene «Mis planes»: si cae en otra sección (p. ej. /admin/bandeja), se la lleva allí.
          <Navigate to="/admin/eventos" replace />
        ) : (
          <>
            <h2 className="titulo-caja">Zona del ayuntamiento y las asociaciones</h2>
            <p>
              Aquí se revisan los planes que llegan por WhatsApp, Telegram o la web, se aprueban las asociaciones y se
              ven las cifras de la agenda.
            </p>
            <IonButton expand="block" size="large" onClick={abrirCuenta}>
              Entrar con mi móvil
            </IonButton>
            <p className="nota-demo">Para la demo, entra sin cuenta con uno de estos papeles:</p>
            <IonButton expand="block" fill="outline" onClick={() => entrarDemo('moderador')}>
              🏛️ Moderación del ayuntamiento
            </IonButton>
            <IonButton expand="block" fill="outline" onClick={() => entrarDemo('publicador')}>
              🤝 Asociación (Amigos de Velefique)
            </IonButton>
            <IonButton expand="block" fill="clear" routerLink="/agenda">
              Volver a la agenda
            </IonButton>
          </>
        )}
      </IonCardContent>
    </IonCard>
  );
};

export default PaginaAdmin;
