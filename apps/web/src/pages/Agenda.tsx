import {
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonList,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSearchbar,
  IonSpinner,
  IonText,
  IonTitle,
  IonToolbar,
  useIonViewWillEnter,
} from '@ionic/react';
import { addCircleOutline } from 'ionicons/icons';
import { useCallback, useEffect, useRef, useState } from 'react';

import { getEventos, misPlanes, MUNICIPIOS } from '../api/client';
import type { Categoria, Evento } from '../api/types';
import CarruselPlanes from '../components/CarruselPlanes';
import FiltrosEventos from '../components/FiltrosEventos';
import { CabeceraPueblo, TarjetasPueblos } from '../components/FotosPueblo';
import Marca from '../components/Marca';
import ParaTi from '../components/ParaTi';
import RecuerdosAgenda from '../components/RecuerdosAgenda';
import SelectorLetra from '../components/SelectorLetra';
import Sugeridos from '../components/Sugeridos';
import TarjetaEvento from '../components/TarjetaEvento';
import TusPlanes from '../components/TusPlanes';
import { useSesion } from '../cuenta/sesion';
import { coincideBusqueda } from '../utils/busqueda';
import { guardarFiltros, leerFiltros } from '../utils/filtrosGuardados';
import { agruparPorDia, claveDia, fechaLarga, yaPaso } from '../utils/formato';
import { usePantallaGrande } from '../utils/pantalla';

const DESTACADOS = 5;

/** «Hoy» o «Mañana» cuando toca: es lo primero que busca quien mira la agenda. */
function diaRelativo(dia: string): string | null {
  const hoy = new Date();
  const manana = new Date(hoy);
  manana.setDate(hoy.getDate() + 1);
  if (dia === claveDia(hoy.toISOString())) return 'Hoy';
  if (dia === claveDia(manana.toISOString())) return 'Mañana';
  return null;
}

/* Cabecera de cada día con una hoja de taco de calendario, como el que cuelga en la cocina. */
const CabeceraDia: React.FC<{ dia: string; iso: string }> = ({ dia, iso }) => {
  const fecha = new Date(iso);
  const mes = fecha.toLocaleDateString('es-ES', { month: 'short', timeZone: 'Europe/Madrid' }).replace('.', '');
  const num = fecha.toLocaleDateString('es-ES', { day: 'numeric', timeZone: 'Europe/Madrid' });
  const relativo = diaRelativo(dia);
  return (
    <header className="cabecera-dia">
      <span className="hoja-dia" aria-hidden="true">
        <span className="hoja-dia__mes">{mes}</span>
        <span className="hoja-dia__num">{num}</span>
      </span>
      <h2 id={`dia-${dia}`} className="cabecera-dia__texto">
        {relativo && <span className="cabecera-dia__relativo">{relativo}</span>}
        <span className="dia">{fechaLarga(iso)}</span>
      </h2>
    </header>
  );
};

const Agenda: React.FC = () => {
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // P1: se abre con el último pueblo y tipo de plan que eligió la persona en este dispositivo.
  const [municipio, setMunicipio] = useState<string | undefined>(() => leerFiltros(MUNICIPIOS).municipio);
  const [categoria, setCategoria] = useState<Categoria | undefined>(() => leerFiltros(MUNICIPIOS).categoria);
  const [busqueda, setBusqueda] = useState('');
  // Todos los próximos planes, sin filtros: alimentan «Tus planes» y el carrusel.
  const [todos, setTodos] = useState<Evento[]>([]);
  const { usuario } = useSesion();
  // N1: en pantalla grande, tres zonas; en el móvil y en la APK la agenda se queda como estaba.
  const grande = usePantallaGrande();
  // Sube al volver a la agenda o al deslizar: «Para ti» cambia cuando la persona se apunta a algo.
  const [recarga, setRecarga] = useState(0);
  const contenido = useRef<HTMLIonContentElement>(null);
  // El logo vuelve al inicio: sin filtros ni búsqueda y arriba del todo.
  const irAlInicio = () => {
    setMunicipio(undefined);
    setCategoria(undefined);
    setBusqueda('');
    void contenido.current?.scrollToTop(300);
  };

  const cargar = useCallback(
    () =>
      getEventos({ municipio, categoria })
        .then((pagina) => {
          setEventos(pagina.items);
          setError(null);
        })
        .catch(() => setError('No hemos podido cargar la agenda. Inténtalo de nuevo en un momento.'))
        .finally(() => setCargando(false)),
    [municipio, categoria],
  );

  useEffect(() => guardarFiltros({ municipio, categoria }), [municipio, categoria]);

  useEffect(() => {
    getEventos({ municipio, categoria })
      .then((pagina) => {
        setEventos(pagina.items);
        setError(null);
      })
      .catch(() => setError('No hemos podido cargar la agenda. Inténtalo de nuevo en un momento.'))
      .finally(() => setCargando(false));
  }, [municipio, categoria]);

  const cargarTodos = useCallback(async () => {
    try {
      const pagina = await getEventos({});
      setTodos(pagina.items.filter((e) => !yaPaso(e)));
    } catch {
      /* el error ya se enseña con la agenda */
    }
  }, []);

  // También al volver de la ficha tras apuntarse («Tus planes») o de la bandeja tras aprobar un plan (la agenda).
  useIonViewWillEnter(() => {
    setRecarga((n) => n + 1);
    void Promise.all([cargar(), cargarTodos()]);
  }, [cargar, cargarTodos]);

  const proximos = eventos.filter((e) => !yaPaso(e) && coincideBusqueda(e, busqueda));
  const mios = misPlanes();
  const tusPlanes = todos.filter((e) => mios.has(e.id));
  const destacados = todos.slice(0, DESTACADOS);

  const saludo = (
    <>
      <SelectorLetra />
      <h1 className="saludo">
        {usuario ? `¡Hola, ${usuario.nombre.split(' ')[0]}! ` : ''}¿Qué hacemos hoy en el pueblo?
      </h1>
    </>
  );

  const carrusel = destacados.length > 0 && (
    <>
      <h2 className="titulo-seccion">Próximos planes</h2>
      <CarruselPlanes eventos={destacados} />
    </>
  );

  const agenda = (
    <>
      {municipio ? (
        <CabeceraPueblo municipio={municipio} />
      ) : (
        <TarjetasPueblos municipio={municipio} onMunicipio={setMunicipio} />
      )}

      <IonSearchbar
        className="buscador-agenda"
        placeholder="Buscar un plan: ruta, teatro, mercado…"
        aria-label="Buscar un plan"
        value={busqueda}
        debounce={150}
        onIonInput={(ev) => setBusqueda(ev.detail.value ?? '')}
      />

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
      {!cargando && !error && proximos.length === 0 && (
        <p className="ion-padding">
          {busqueda.trim()
            ? `No encontramos «${busqueda.trim()}» en los próximos planes. Prueba con otra palabra o quita los filtros.`
            : 'No hay planes con estos filtros. Prueba con otro pueblo o categoría.'}
        </p>
      )}

      <div className="agenda-dias">
        {agruparPorDia(proximos).map(([dia, delDia]) => (
          <section key={dia} className="grupo-dia" aria-labelledby={`dia-${dia}`}>
            <CabeceraDia dia={dia} iso={delDia[0].fecha_inicio} />
            <IonList lines="none" className="grupo-dia__planes">
              {delDia.map((e) => (
                <TarjetaEvento key={e.id} evento={e} />
              ))}
            </IonList>
          </section>
        ))}
      </div>
    </>
  );

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>
            <Marca onInicio={irAlInicio} />
          </IonTitle>
          <IonButtons slot="end">
            <IonButton routerLink="/proponer" fill="outline" className="boton-proponer" aria-label="Proponer un plan">
              <IonIcon slot="start" icon={addCircleOutline} aria-hidden="true" />
              <span className="texto-boton">Proponer</span>
            </IonButton>
          </IonButtons>
        </IonToolbar>
      </IonHeader>
      <IonContent ref={contenido} className={grande ? 'contenido-agenda contenido-agenda--zonas' : 'contenido-agenda'}>
        <IonRefresher
          slot="fixed"
          onIonRefresh={(ev) => {
            setRecarga((n) => n + 1);
            void Promise.all([cargar(), cargarTodos()]).then(() => ev.detail.complete());
          }}
        >
          <IonRefresherContent />
        </IonRefresher>

        {grande ? (
          <div className="agenda-zonas">
            <aside className="agenda-zonas__lateral" aria-label="Tus planes y sugeridos">
              <TusPlanes eventos={tusPlanes} />
              <Sugeridos usuario={usuario} proximos={todos} mios={mios} recarga={recarga} />
              <RecuerdosAgenda compacto />
            </aside>
            <div className="agenda-zonas__centro">
              <div className="inicio">
                {saludo}
                {carrusel}
              </div>
              {agenda}
            </div>
          </div>
        ) : (
          <>
            <div className="inicio">
              {saludo}
              <TusPlanes eventos={tusPlanes} />
              {usuario && <ParaTi usuarioId={usuario.id} recarga={recarga} />}
              {carrusel}
            </div>
            {agenda}
          </>
        )}
      </IonContent>
    </IonPage>
  );
};

export default Agenda;
