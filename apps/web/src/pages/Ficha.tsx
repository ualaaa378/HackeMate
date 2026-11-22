import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonActionSheet,
  IonAlert,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonTitle,
  IonToast,
  IonToolbar,
  useIonViewWillEnter,
} from '@ionic/react';
import {
  calendarOutline,
  checkmarkCircle,
  globeOutline,
  locationOutline,
  logoFacebook,
  mapOutline,
  shareSocialOutline,
  peopleOutline,
  ticketOutline,
} from 'ionicons/icons';
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { desapuntarse, enModoRespaldo, ErrorApi, getEvento, inscribirse, miInscripcion, urlIcs } from '../api/client';
import { CATEGORIAS, type Evento } from '../api/types';
import { NOMBRE_CANAL } from '../canal';
import BotonMeGusta from '../components/BotonMeGusta';
import ChatEvento from '../components/ChatEvento';
import FotoPlan from '../components/FotoPlan';
import RecuerdoPlan from '../components/RecuerdoPlan';
import { useSesion } from '../cuenta/sesion';
import { enlaceComoLlegar, enlaceEnviarPorCanal } from '../utils/compartir';
import {
  claveDia,
  fechaEstimada,
  fechaLarga,
  hora,
  plazas,
  precio,
  sinHora,
  textoApuntados,
  yaPaso,
} from '../utils/formato';

const mesCorto = (iso: string): string =>
  new Date(iso).toLocaleDateString('es-ES', { month: 'short', timeZone: 'Europe/Madrid' }).replace('.', '');
const diaDelMes = (iso: string): string =>
  new Date(iso).toLocaleDateString('es-ES', { day: 'numeric', timeZone: 'Europe/Madrid' });

const textoFueron = (n: number): string =>
  n === 0 ? 'Nadie se apuntó por la app' : n === 1 ? 'Se apuntó 1 persona' : `Se apuntaron ${n} personas`;

const REFRESCO_FICHA_MS = 20_000;

type EstadoInscripcion = 'confirmada' | 'lista_espera' | 'apuntado';

const Ficha: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [evento, setEvento] = useState<Evento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apuntando, setApuntando] = useState(false);
  // Lo que pasa en esta pantalla manda; si no, lo que recuerda este móvil (apuntado aquí o la API dijo que ya lo estaba).
  const [estados, setEstados] = useState<Record<string, EstadoInscripcion | null>>({});
  const [confirmarBaja, setConfirmarBaja] = useState(false);
  const inscrito: EstadoInscripcion | null =
    id && id in estados ? estados[id] : id && miInscripcion(id) ? 'apuntado' : null;
  const setInscrito = (e: EstadoInscripcion | null) => id && setEstados((xs) => ({ ...xs, [id]: e }));
  const [aviso, setAviso] = useState<string | null>(null);
  const [menuCompartir, setMenuCompartir] = useState(false);
  const { usuario, conCuenta } = useSesion();

  // Plazas, hora y estado cambian por lo que hacen otros (inscripciones, el publicador, el moderador):
  // se vuelve a pedir al entrar en la ficha, al deslizar hacia abajo y cada poco mientras está abierta.
  const cargar = useCallback(
    (primera = false): Promise<void> =>
      id
        ? getEvento(id)
            .then(setEvento)
            .catch(() => {
              if (primera) setError('No encontramos este plan.');
            })
        : Promise.resolve(),
    [id],
  );

  useEffect(() => {
    if (id)
      getEvento(id)
        .then(setEvento)
        .catch(() => setError('No encontramos este plan.'));
    const reloj = setInterval(() => {
      if (document.visibilityState === 'visible') void cargar();
    }, REFRESCO_FICHA_MS);
    return () => clearInterval(reloj);
  }, [id, cargar]);

  useIonViewWillEnter(() => void cargar(), [cargar]);

  const apuntarme = () => {
    conCuenta(
      'Para apuntarte a este plan necesitas una cuenta. Así la organización sabe quién va y te avisamos si algo cambia.',
      () => void apuntar(),
    );
  };

  const apuntar = async () => {
    if (!evento) return;
    setApuntando(true);
    try {
      const insc = await inscribirse(evento.id);
      setInscrito(insc.estado === 'lista_espera' ? 'lista_espera' : 'confirmada');
      setAviso(insc.estado === 'lista_espera' ? 'Estás en la lista de espera' : '¡Plaza confirmada!');
      setEvento(await getEvento(evento.id));
    } catch (e) {
      if (e instanceof ErrorApi && e.code === 'ya_inscrito') {
        setInscrito('apuntado');
        setAviso('Ya estabas apuntado a este plan');
      } else {
        setAviso('No hemos podido apuntarte. Inténtalo de nuevo.');
      }
    } finally {
      setApuntando(false);
    }
  };

  const desapuntar = async () => {
    if (!evento) return;
    setApuntando(true);
    try {
      await desapuntarse(evento.id);
      setInscrito(null);
      setAviso('Te has desapuntado. Tu plaza queda libre para otra persona.');
      setEvento(await getEvento(evento.id));
    } catch {
      setAviso('No hemos podido desapuntarte. Inténtalo de nuevo.');
    } finally {
      setApuntando(false);
    }
  };

  const pasado = !!evento && yaPaso(evento);
  const enlaceMapa = evento ? enlaceComoLlegar(evento.lat, evento.lon) : '#';
  const textoCompartir = evento ? `${evento.titulo} · ${fechaLarga(evento.fecha_inicio)} en ${evento.municipio}` : '';

  // P1: el menú del móvil para compartir si existe; si no (ordenador), el canal configurado o copiar el enlace.
  const compartir = async () => {
    if (!evento) return;
    const url = window.location.href;
    if (typeof navigator.share === 'function') {
      try {
        await navigator.share({ title: evento.titulo, text: textoCompartir, url });
      } catch {
        /* la persona cerró el menú sin compartir */
      }
      return;
    }
    setMenuCompartir(true);
  };

  const copiarEnlace = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setAviso('Enlace copiado. Pégalo donde quieras.');
    } catch {
      setAviso('No hemos podido copiar el enlace. Cópialo de la barra de direcciones.');
    }
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <IonBackButton defaultHref="/agenda" text="Volver" />
          </IonButtons>
          <IonTitle>Plan</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding contenido-lectura">
        <IonRefresher slot="fixed" onIonRefresh={(ev) => void cargar().then(() => ev.detail.complete())}>
          <IonRefresherContent />
        </IonRefresher>
        {!evento && !error && (
          <div className="centrado">
            <IonSpinner aria-label="Cargando" />
          </div>
        )}
        {error && <p>{error}</p>}
        {evento && (
          <>
            <FotoPlan evento={evento} className="foto-plan--ficha" />
            {pasado && (
              <p className="aviso-pasado" role="status">
                📸 Este plan ya pasó. Ya no se puede apuntar nadie, pero puedes ver las fotos y dejar un comentario.
              </p>
            )}
            <article className="ficha" aria-labelledby="ficha-titulo">
              <span className="ficha__categoria" style={{ background: CATEGORIAS[evento.categoria].color }}>
                {CATEGORIAS[evento.categoria].emoji} {CATEGORIAS[evento.categoria].etiqueta}
              </span>
              <h1 id="ficha-titulo" className="ficha__titulo">
                {evento.titulo}
              </h1>
              {evento.publicador_nombre && <p className="ficha__organiza">Organiza {evento.publicador_nombre}</p>}
              <BotonMeGusta eventoId={evento.id} />

              <dl className="ficha__datos">
                <div>
                  <dt>
                    <span className="hoja-dia hoja-dia--peque" aria-hidden="true">
                      <span className="hoja-dia__mes">{mesCorto(evento.fecha_inicio)}</span>
                      <span className="hoja-dia__num">{diaDelMes(evento.fecha_inicio)}</span>
                    </span>
                    <span className="oculto-visual">Cuándo</span>
                  </dt>
                  <dd>
                    <strong className="dia">{fechaLarga(evento.fecha_inicio)}</strong>
                    <span>
                      {sinHora(evento) ? 'Hora por confirmar' : `A las ${hora(evento.fecha_inicio)}`}
                      {evento.fecha_fin &&
                        (claveDia(evento.fecha_fin) !== claveDia(evento.fecha_inicio)
                          ? `, hasta el ${fechaLarga(evento.fecha_fin)}`
                          : !sinHora(evento) && `, hasta las ${hora(evento.fecha_fin)}`)}
                    </span>
                    {fechaEstimada(evento) && (
                      <span className="ficha__nota">
                        Fecha estimada según el calendario de fiestas, pendiente de confirmar
                      </span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>
                    <IonIcon icon={locationOutline} aria-hidden="true" />
                    <span className="oculto-visual">Dónde</span>
                  </dt>
                  <dd>
                    <strong>{evento.lugar ?? evento.municipio}</strong>
                    {evento.lugar && <span>{evento.municipio}</span>}
                  </dd>
                </div>
                {!pasado && (
                  <div>
                    <dt>
                      <IonIcon icon={ticketOutline} aria-hidden="true" />
                      <span className="oculto-visual">Precio</span>
                    </dt>
                    <dd>
                      <strong>
                        {evento.es_gratuito || evento.precio_eur != null ? precio(evento) : 'Precio por confirmar'}
                      </strong>
                      {plazas(evento) && <span>{plazas(evento)}</span>}
                    </dd>
                  </div>
                )}
                <div>
                  <dt>
                    <IonIcon icon={peopleOutline} aria-hidden="true" />
                    <span className="oculto-visual">Gente</span>
                  </dt>
                  <dd>
                    <strong className="contador-ficha">
                      {pasado ? textoFueron(evento.inscritos ?? 0) : textoApuntados(evento)}
                    </strong>
                  </dd>
                </div>
              </dl>
              {evento.descripcion && <p className="descripcion">{evento.descripcion}</p>}
            </article>

            {!pasado && (
              <>
                <div className={inscrito ? undefined : 'ficha__apuntarme'}>
                  <IonButton
                    expand="block"
                    size="large"
                    onClick={apuntarme}
                    disabled={apuntando || !!inscrito}
                    color={inscrito ? 'success' : 'primary'}
                  >
                    {apuntando ? (
                      <IonSpinner name="dots" />
                    ) : inscrito ? (
                      <>
                        <IonIcon slot="start" icon={checkmarkCircle} aria-hidden="true" />
                        {inscrito === 'lista_espera' ? 'En lista de espera' : 'Ya estás apuntado'}
                      </>
                    ) : (
                      '🙋 Apuntarme'
                    )}
                  </IonButton>
                </div>
                {inscrito && miInscripcion(evento.id) && (
                  <IonButton
                    expand="block"
                    fill="outline"
                    color="medium"
                    disabled={apuntando}
                    onClick={() => setConfirmarBaja(true)}
                  >
                    Desapuntarme
                  </IonButton>
                )}
                <IonAlert
                  isOpen={confirmarBaja}
                  onDidDismiss={() => setConfirmarBaja(false)}
                  header="¿Te desapuntas?"
                  message="Tu plaza quedará libre para otra persona. Podrás volver a apuntarte si sigue habiendo sitio."
                  buttons={[
                    { text: 'No, sigo apuntado', role: 'cancel' },
                    { text: 'Sí, desapuntarme', role: 'destructive', handler: () => void desapuntar() },
                  ]}
                />
                {!usuario && !inscrito && (
                  <p className="candado">🔒 Para apuntarte te pediremos crear una cuenta. Solo se tarda un momento.</p>
                )}
                <IonButton
                  expand="block"
                  fill="outline"
                  href={urlIcs(evento.id)}
                  disabled={enModoRespaldo()}
                  download={`${evento.titulo}.ics`}
                >
                  <IonIcon slot="start" icon={calendarOutline} aria-hidden="true" />
                  Añadir a mi calendario
                </IonButton>
                <IonButton expand="block" fill="clear" href={enlaceMapa} target="_blank" rel="noopener">
                  <IonIcon slot="start" icon={mapOutline} aria-hidden="true" />
                  Cómo llegar
                </IonButton>
              </>
            )}
            <IonButton expand="block" fill="clear" onClick={() => void compartir()}>
              <IonIcon slot="start" icon={shareSocialOutline} aria-hidden="true" />
              Compartir este plan
            </IonButton>
            <IonActionSheet
              isOpen={menuCompartir}
              onDidDismiss={() => setMenuCompartir(false)}
              header="Compartir este plan"
              buttons={[
                {
                  text: `Enviar por ${NOMBRE_CANAL}`,
                  handler: () => {
                    window.open(enlaceEnviarPorCanal(textoCompartir, window.location.href), '_blank', 'noopener');
                  },
                },
                { text: 'Copiar enlace', handler: () => void copiarEnlace() },
                { text: 'Cancelar', role: 'cancel' },
              ]}
            />
            {evento.origen.url && (
              <IonButton expand="block" fill="clear" href={evento.origen.url} target="_blank" rel="noopener">
                <IonIcon
                  slot="start"
                  icon={evento.origen.canal === 'facebook' ? logoFacebook : globeOutline}
                  aria-hidden="true"
                />
                Ver fuente original
              </IonButton>
            )}
            {pasado ? <RecuerdoPlan evento={evento} /> : <ChatEvento eventoId={evento.id} />}
          </>
        )}
        <IonToast isOpen={!!aviso} message={aviso ?? ''} duration={2500} onDidDismiss={() => setAviso(null)} />
      </IonContent>
    </IonPage>
  );
};

export default Ficha;
