import {
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonItemDivider,
  IonLabel,
  IonList,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonText,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { addCircleOutline } from 'ionicons/icons';
import { useCallback, useEffect, useState } from 'react';

import { getEventos } from '../api/client';
import type { Categoria, Evento } from '../api/types';
import FiltrosEventos from '../components/FiltrosEventos';
import Marca from '../components/Marca';
import TarjetaEvento from '../components/TarjetaEvento';
import { agruparPorDia, fechaLarga } from '../utils/formato';

const Agenda: React.FC = () => {
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [municipio, setMunicipio] = useState<string>();
  const [categoria, setCategoria] = useState<Categoria>();

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const pagina = await getEventos({ municipio, categoria });
      setEventos(pagina.items);
    } catch {
      setError('No hemos podido cargar la agenda. Inténtalo de nuevo en un momento.');
    } finally {
      setCargando(false);
    }
  }, [municipio, categoria]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>
            <Marca />
          </IonTitle>
          <IonButtons slot="end">
            <IonButton routerLink="/proponer" fill="outline" className="boton-proponer" aria-label="Proponer un plan">
              <IonIcon slot="start" icon={addCircleOutline} aria-hidden="true" />
              <span className="texto-boton">Proponer</span>
            </IonButton>
          </IonButtons>
        </IonToolbar>
      </IonHeader>
      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={(ev) => void cargar().then(() => ev.detail.complete())}>
          <IonRefresherContent />
        </IonRefresher>

        <FiltrosEventos
          municipio={municipio}
          categoria={categoria}
          onMunicipio={setMunicipio}
          onCategoria={setCategoria}
        />

        {cargando && (
          <div className="centrado">
            <IonSpinner aria-label="Cargando" />
          </div>
        )}
        {error && (
          <IonText color="danger">
            <p className="ion-padding">{error}</p>
          </IonText>
        )}
        {!cargando && !error && eventos.length === 0 && (
          <p className="ion-padding">No hay planes con estos filtros. Prueba con otro pueblo o categoría.</p>
        )}

        <IonList>
          {agruparPorDia(eventos).map(([dia, delDia]) => (
            <div key={dia}>
              <IonItemDivider sticky color="light">
                <IonLabel className="dia">{fechaLarga(delDia[0].fecha_inicio)}</IonLabel>
              </IonItemDivider>
              {delDia.map((e) => (
                <TarjetaEvento key={e.id} evento={e} />
              ))}
            </div>
          ))}
        </IonList>
      </IonContent>
    </IonPage>
  );
};

export default Agenda;
