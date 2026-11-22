import { IonButton, IonContent, IonHeader, IonIcon, IonModal, IonTitle, IonToolbar } from '@ionic/react';
import { close } from 'ionicons/icons';
import { useCallback } from 'react';

import type { Evento } from '../api/types';

import RecuerdoPlan from './RecuerdoPlan';

/** Hoja con las fotos y los comentarios de un plan pasado. La usan la pestaña Recuerdos y la agenda de escritorio. */
const ComentariosRecuerdo: React.FC<{
  evento: Evento | null;
  onCerrar: () => void;
  onNuevo: (eventoId: string, total: number) => void;
}> = ({ evento, onCerrar, onNuevo }) => {
  const id = evento?.id;
  const alCambiar = useCallback((n: number) => id && onNuevo(id, n), [id, onNuevo]);
  return (
    <IonModal
      isOpen={!!evento}
      onDidDismiss={onCerrar}
      initialBreakpoint={0.75}
      breakpoints={[0, 0.5, 0.75, 1]}
      className="hoja-comentarios"
    >
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>Fotos y comentarios</IonTitle>
          <IonButton slot="end" fill="clear" color="light" onClick={onCerrar} aria-label="Cerrar">
            <IonIcon icon={close} aria-hidden="true" />
          </IonButton>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        {evento && (
          <>
            <p className="hoja-comentarios__plan">{evento.titulo}</p>
            <RecuerdoPlan evento={evento} onTotal={alCambiar} />
          </>
        )}
      </IonContent>
    </IonModal>
  );
};

export default ComentariosRecuerdo;
