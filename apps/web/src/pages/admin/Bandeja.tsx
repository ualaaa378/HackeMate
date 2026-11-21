import {
  IonAlert,
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardSubtitle,
  IonCardTitle,
  IonChip,
  IonSpinner,
  IonText,
  IonToast,
} from '@ionic/react';
import { useCallback, useEffect, useRef, useState } from 'react';

import BloqueConfianza from '../../admin/BloqueConfianza';
import PaginaAdmin from '../../admin/PaginaAdmin';
import { useAcceso } from '../../admin/acceso';
import { EVENTO_BANDEJA } from '../../admin/pendientes';
import { aprobarPublicador, decidir, getPendientes } from '../../api/admin';
import { CATEGORIAS, NECESIDADES, PUBLICOS, type PendienteBandeja } from '../../api/types';
import { fechaLarga, horaEvento, precio } from '../../utils/formato';

const CANALES: Record<string, string> = {
  whatsapp: '💬 WhatsApp',
  telegram: '✈️ Telegram',
  web: '🌐 Propuesta desde la app',
  panel: '🏛️ Panel',
  facebook: '📘 Facebook',
  instagram: '📸 Instagram',
  web_externa: '🔗 Web del pueblo',
  manual: '✍️ A mano',
};

const ENTIDADES = {
  particular: 'A título personal',
  asociacion: 'Asociación',
  comercio: 'Comercio',
  otra: 'Otra entidad',
};
const SEGURO = { si: 'Sí', no: 'No', nose: 'No lo sabe' };

function nivelSpam(score: number | null | undefined): { texto: string; clase: string } | null {
  if (score == null) return null;
  const pct = Math.round(score * 100);
  if (score >= 0.7) return { texto: `Riesgo de spam alto (${pct} %)`, clase: 'spam spam--alto' };
  if (score >= 0.3) return { texto: `Riesgo de spam medio (${pct} %)`, clase: 'spam spam--medio' };
  return { texto: `Riesgo de spam bajo (${pct} %)`, clase: 'spam spam--bajo' };
}

/** N9b/N9c: la API empieza el motivo por «Posible fraude» cuando la IA ve señales de estafa. */
const esApelacion = (p: PendienteBandeja) => p.motivo.trimStart().toLowerCase().startsWith('apelación:');
const esFraude = (p: PendienteBandeja) => p.motivo.trimStart().toLowerCase().startsWith('posible fraude');

const clave = (p: PendienteBandeja) => p.evento?.id ?? p.publicador?.id ?? p.motivo;

const Bandeja: React.FC = () => {
  const [items, setItems] = useState<PendienteBandeja[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [rechazando, setRechazando] = useState<PendienteBandeja | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);

  const { rol } = useAcceso();

  // Se carga al entrar con un rol: la página existe antes de que se elija moderador en la puerta.
  const cargar = useCallback(() => {
    if (rol !== 'moderador') return;
    getPendientes()
      .then((p) => setItems(p.items))
      .catch(() => setError('No hemos podido cargar la bandeja.'));
  }, [rol]);

  // Los posts nuevos (bot, Facebook, web) llegan solos, como en el Panel. No se refresca mientras
  // el moderador decide uno, para que la tarjeta no le cambie debajo del dedo.
  const decidiendo = useRef(false);
  useEffect(() => {
    decidiendo.current = ocupado !== null || rechazando !== null;
  }, [ocupado, rechazando]);
  useEffect(() => {
    cargar();
    const t = setInterval(() => {
      if (!decidiendo.current && document.visibilityState === 'visible') cargar();
    }, 10_000);
    return () => clearInterval(t);
  }, [cargar]);

  const quitar = (p: PendienteBandeja) => setItems((xs) => xs?.filter((x) => x !== p) ?? null);

  const actuar = async (p: PendienteBandeja, aprobar: boolean, motivo?: string) => {
    setOcupado(clave(p));
    try {
      if (p.evento) {
        await decidir(p.evento.id, { decision: aprobar ? 'aprobar' : 'rechazar', motivo: motivo || null });
        setAviso(aprobar ? `«${p.evento.titulo}» ya está en la agenda.` : `«${p.evento.titulo}» rechazado.`);
      } else if (p.publicador) {
        await aprobarPublicador(p.publicador.id, { aprobar, motivo: motivo || null });
        setAviso(aprobar ? `${p.publicador.nombre} ya puede publicar.` : `${p.publicador.nombre} rechazado.`);
      }
      quitar(p);
      window.dispatchEvent(new Event(EVENTO_BANDEJA));
    } catch (e) {
      setAviso(e instanceof Error ? e.message : 'No se ha podido guardar.');
    } finally {
      setOcupado(null);
    }
  };

  return (
    <PaginaAdmin titulo="📥 Bandeja" roles={['moderador']}>
      <p className="intro-admin">
        Lo que la IA no puede decidir sola. Lee el motivo y decide: lo aprobado sale en la agenda al momento.
      </p>
      {!items && !error && (
        <div className="centrado">
          <IonSpinner aria-label="Cargando" />
        </div>
      )}
      {error && (
        <IonText color="danger">
          <p>{error}</p>
        </IonText>
      )}
      {items?.length === 0 && <p className="vacio-admin">✅ No hay nada pendiente. Buen trabajo.</p>}

      {items?.map((p) => {
        const e = p.evento;
        const spam = nivelSpam(p.score_spam);
        // El botón relleno es el que recomienda la IA; la persona sigue decidiendo.
        const sospechoso = (p.score_spam != null && p.score_spam >= 0.7) || esFraude(p);
        return (
          <IonCard key={clave(p)} className={`pendiente ${sospechoso ? 'pendiente--spam' : ''}`}>
            <IonCardHeader>
              {e ? (
                <>
                  <div className="chips-pendiente">
                    <IonChip style={{ background: CATEGORIAS[e.categoria].color, color: '#fff' }}>
                      {CATEGORIAS[e.categoria].emoji} {CATEGORIAS[e.categoria].etiqueta}
                    </IonChip>
                    <IonChip outline>{CANALES[e.origen.canal] ?? e.origen.canal}</IonChip>
                    {esFraude(p) && <IonChip className="chip-fraude">⚠️ Posible fraude</IonChip>}
                    {esApelacion(p) && <IonChip className="chip-apelacion">🔁 Apelación</IonChip>}
                  </div>
                  <IonCardTitle>{e.titulo}</IonCardTitle>
                  <IonCardSubtitle>
                    {e.publicador_nombre ?? 'Sin publicador'} · 📍 {e.municipio}
                  </IonCardSubtitle>
                </>
              ) : (
                p.publicador && (
                  <>
                    <IonChip outline>🤝 Nueva asociación o comercio</IonChip>
                    <IonCardTitle>{p.publicador.nombre}</IonCardTitle>
                    <IonCardSubtitle>📍 {p.publicador.municipio}</IonCardSubtitle>
                  </>
                )
              )}
            </IonCardHeader>
            <IonCardContent>
              {e && (
                <p className="datos-pendiente">
                  📅 {fechaLarga(e.fecha_inicio)} · 🕘 {horaEvento(e)}
                  {e.lugar && ` · ${e.lugar}`} · {precio(e)}
                </p>
              )}
              {e?.descripcion && <p className="descripcion">{e.descripcion}</p>}
              {p.publicador?.descripcion && <p className="descripcion">{p.publicador.descripcion}</p>}
              {p.publicador && <BloqueConfianza publicador={p.publicador} conRequisitos={false} />}

              <div className="motivo-ia">
                <strong>🤖 Por qué está aquí</strong>
                <p>{p.motivo}</p>
                {spam && <IonBadge className={spam.clase}>{spam.texto}</IonBadge>}
              </div>

              {p.propuesta && (
                <details className="propuesta">
                  <summary>Datos para el ayuntamiento</summary>
                  <dl>
                    <dt>Responsable</dt>
                    <dd>
                      {p.propuesta.responsable} · {p.propuesta.telefono}
                    </dd>
                    <dt>Quién lo organiza</dt>
                    <dd>
                      {ENTIDADES[p.propuesta.entidad]}
                      {p.propuesta.entidad_nombre && ` · ${p.propuesta.entidad_nombre}`}
                    </dd>
                    <dt>Público</dt>
                    <dd>{PUBLICOS[p.propuesta.publico]}</dd>
                    <dt>Necesita</dt>
                    <dd>
                      {p.propuesta.necesidades.length
                        ? p.propuesta.necesidades.map((n) => NECESIDADES[n]).join(' · ')
                        : 'Nada del ayuntamiento'}
                    </dd>
                    <dt>Seguro de responsabilidad civil</dt>
                    <dd>{SEGURO[p.propuesta.seguro_rc]}</dd>
                    {p.propuesta.observaciones && (
                      <>
                        <dt>Observaciones</dt>
                        <dd>{p.propuesta.observaciones}</dd>
                      </>
                    )}
                  </dl>
                </details>
              )}

              <div className="botones-decision">
                <IonButton
                  color="success"
                  size="large"
                  fill={sospechoso ? 'outline' : 'solid'}
                  disabled={ocupado === clave(p)}
                  onClick={() => void actuar(p, true)}
                >
                  ✔ Aprobar
                </IonButton>
                <IonButton
                  color="danger"
                  size="large"
                  fill={sospechoso ? 'solid' : 'outline'}
                  disabled={ocupado === clave(p)}
                  onClick={() => setRechazando(p)}
                >
                  ✖ Rechazar
                </IonButton>
              </div>
            </IonCardContent>
          </IonCard>
        );
      })}

      <IonAlert
        isOpen={rechazando != null}
        header="¿Rechazar?"
        message="Puedes explicar el motivo. Se le enviará a quien lo publicó."
        inputs={[{ name: 'motivo', type: 'textarea', placeholder: 'Motivo (opcional)' }]}
        buttons={[
          { text: 'Volver', role: 'cancel' },
          {
            text: 'Rechazar',
            role: 'destructive',
            handler: (datos: { motivo?: string }) => {
              if (rechazando) void actuar(rechazando, false, datos.motivo);
            },
          },
        ]}
        onDidDismiss={() => setRechazando(null)}
      />
      <IonToast isOpen={aviso != null} message={aviso ?? ''} duration={3000} onDidDismiss={() => setAviso(null)} />
    </PaginaAdmin>
  );
};

export default Bandeja;
