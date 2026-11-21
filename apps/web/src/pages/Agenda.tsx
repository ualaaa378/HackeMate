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
  useIonViewWillEnter,
} from '@ionic/react';
import { addCircleOutline } from 'ionicons/icons';
import { useCallback, useEffect, useState } from 'react';

import { getEventos, misPlanes } from '../api/client';
import type { Categoria, Evento } from '../api/types';
import CarruselPlanes from '../components/CarruselPlanes';
import FiltrosEventos from '../components/FiltrosEventos';
import { CabeceraPueblo, TarjetasPueblos } from '../components/FotosPueblo';
import Marca from '../components/Marca';
import SelectorLetra from '../components/SelectorLetra';
import TarjetaEvento from '../components/TarjetaEvento';
import TusPlanes from '../components/TusPlanes';
import { useSesion } from '../cuenta/sesion';
import { agruparPorDia, fechaLarga, yaPaso } from '../utils/formato';

const DESTACADOS = 5;

const Agenda: React.FC = () => {
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [municipio, setMunicipio] = useState<string>();
  const [categoria, setCategoria] = useState<Categoria>();
  // Todos los próximos planes, sin filtros: alimentan «Tus planes» y el carrusel.
  const [todos, setTodos] = useState<Evento[]>([]);
  const { usuario } = useSesion();

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

  const cargarTodos = useCallback(async () => {
    try {
      const pagina = await getEventos({});
      setTodos(pagina.items.filter((e) => !yaPaso(e)));
    } catch {
      /* el error ya se enseña con la agenda */
    }
  }, []);

  // También al volver de la ficha tras apuntarse («Tus planes») o de la bandeja tras aprobar un plan (la agenda).
  useIonViewWillEnter(() => void Promise.all([cargar(), cargarTodos()]), [cargar, cargarTodos]);

  const mios = misPlanes();
  const tusPlanes = todos.filter((e) => mios.has(e.id));
  const destacados = todos.slice(0, DESTACADOS);

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
        <IonRefresher
          slot="fixed"
          onIonRefresh={(ev) => void Promise.all([cargar(), cargarTodos()]).then(() => ev.detail.complete())}
        >
          <IonRefresherContent />
        </IonRefresher>

        <div className="inicio">
          <SelectorLetra />
          <h1 className="saludo">
            {usuario ? `¡Hola, ${usuario.nombre.split(' ')[0]}! ` : ''}¿Qué hacemos hoy en el pueblo?
          </h1>
          <TusPlanes eventos={tusPlanes} />
          {destacados.length > 0 && (
            <>
              <h2 className="titulo-seccion">Próximos planes</h2>
              <CarruselPlanes eventos={destacados} />
            </>
          )}
        </div>

        {municipio ? (
          <CabeceraPueblo municipio={municipio} />
        ) : (
          <TarjetasPueblos municipio={municipio} onMunicipio={setMunicipio} />
        )}

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
