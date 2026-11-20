import { IonContent, IonHeader, IonPage, IonTitle, IonToolbar } from '@ionic/react';

// Bloque 3: login con Google, gustos, pueblo, tipo de avisos y vincular WhatsApp.
const Perfil: React.FC = () => (
  <IonPage>
    <IonHeader>
      <IonToolbar color="secondary">
        <IonTitle>👤 Mi perfil</IonTitle>
      </IonToolbar>
    </IonHeader>
    <IonContent className="ion-padding">
      <p>Aquí podrás entrar con Google, elegir tus gustos y decidir qué avisos te llegan por WhatsApp.</p>
    </IonContent>
  </IonPage>
);

export default Perfil;
