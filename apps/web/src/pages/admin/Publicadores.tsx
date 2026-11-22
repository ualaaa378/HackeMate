import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardSubtitle,
  IonCardTitle,
  IonSpinner,
  IonToast,
  IonToggle,
} from '@ionic/react';
import { useEffect, useState } from 'react';

import BloqueConfianza from '../../admin/BloqueConfianza';
import PaginaAdmin from '../../admin/PaginaAdmin';
import { useAcceso } from '../../admin/acceso';
import { deberiaVolverAManual, modoRevision, puedeSerAutomatica } from '../../admin/confianza';
import {
  aprobarPublicador,
  cambiarRevision,
  getPublicadores,
  pausarPublicador,
  verificarIdentidad,
} from '../../api/admin';
import type { Publicador, PublicadorAdmin } from '../../api/types';

const TIPOS: Record<Publicador['tipo'], string> = {
  asociacion: 'Asociación',
  ayuntamiento: 'Ayuntamiento',
  bar_restaurante: 'Bar o restaurante',
  comercio: 'Comercio',
  otro: 'Otro',
};

const ESTADOS: Record<Publicador['estado'], { texto: string; color: string }> = {
  solicitado: { texto: 'Ha pedido acceso', color: 'primary' },
  whatsapp_verificado: { texto: 'Por aprobar', color: 'primary' },
  aprobado: { texto: 'Activo', color: 'success' },
  rechazado: { texto: 'Rechazado', color: 'medium' },
  pausado: { texto: 'Pausado', color: 'danger' },
};

const MODOS = {
  manual: { texto: '✋ Revisión a mano', color: 'medium' },
  automatica: { texto: '⚡ Publica sin revisión', color: 'tertiary' },
} as const;

const Publicadores: React.FC = () => {
  const [lista, setLista] = useState<PublicadorAdmin[] | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const { rol } = useAcceso();
  useEffect(() => {
    if (rol !== 'moderador') return;
    getPublicadores()
      .then((p) => setLista(p.items))
      .catch(() => setLista([]));
  }, [rol]);

  const reemplazar = (p: PublicadorAdmin) => setLista((xs) => xs?.map((x) => (x.id === p.id ? p : x)) ?? null);

  const ejecutar = async (accion: () => Promise<PublicadorAdmin>, texto: (p: PublicadorAdmin) => string) => {
    try {
      const p = await accion();
      reemplazar(p);
      setAviso(texto(p));
    } catch (e) {
      setAviso(e instanceof Error ? e.message : 'No se ha podido guardar.');
    }
  };

  const porAprobar = (p: Publicador) => p.estado === 'solicitado' || p.estado === 'whatsapp_verificado';

  return (
    <PaginaAdmin titulo="🏛️ Ayuntamientos" roles={['moderador']}>
      <p className="intro-admin">
        Quién puede publicar planes: solo ayuntamientos. Las solicitudes nuevas (desde el bot o desde «Dar de alta mi
        ayuntamiento» en la web) salen primero. Todo ayuntamiento empieza con revisión a mano y pasa a publicar sin
        revisión cuando su responsable está identificado y publica a menudo sin rechazos.
      </p>
      {!lista && (
        <div className="centrado">
          <IonSpinner aria-label="Cargando" />
        </div>
      )}
      {lista
        ?.slice()
        .sort((a, b) => Number(porAprobar(b)) - Number(porAprobar(a)) || a.nombre.localeCompare(b.nombre))
        .map((p) => (
          <IonCard key={p.id} className={porAprobar(p) ? 'pendiente' : ''}>
            <IonCardHeader>
              <div className="chips-pendiente">
                <IonBadge color={ESTADOS[p.estado].color}>{ESTADOS[p.estado].texto}</IonBadge>
                {!porAprobar(p) && (
                  <IonBadge color={MODOS[modoRevision(p)].color}>{MODOS[modoRevision(p)].texto}</IonBadge>
                )}
              </div>
              <IonCardTitle>{p.nombre}</IonCardTitle>
              <IonCardSubtitle>
                {TIPOS[p.tipo]} · 📍 {p.municipio}
                {p.aprobaciones != null && ` · ${p.aprobaciones} planes aprobados en total`}
              </IonCardSubtitle>
            </IonCardHeader>
            <IonCardContent>
              {p.descripcion && <p>{p.descripcion}</p>}
              {p.fuentes && p.fuentes.length > 0 && (
                <p className="fuentes">
                  Vigilamos: {p.fuentes.map((f) => f.url.replace(/^https?:\/\/(www\.)?/, '')).join(', ')}
                </p>
              )}

              <BloqueConfianza publicador={p} conRequisitos={!porAprobar(p)} />
              {deberiaVolverAManual(p) && (
                <p className="aviso-confianza" role="alert">
                  ⚠️ Ya no cumple todos los requisitos. Te recomendamos pasarla a revisión a mano.
                </p>
              )}
              <div className="botones-confianza">
                {p.responsable && !p.responsable.identidad_verificada && (
                  <IonButton
                    fill="outline"
                    onClick={() =>
                      void ejecutar(
                        () => verificarIdentidad(p.id),
                        (x) => `Identidad del responsable de ${x.nombre} comprobada.`,
                      )
                    }
                  >
                    🪪 He comprobado su DNI y residencia
                  </IonButton>
                )}
                {p.estado === 'aprobado' && modoRevision(p) === 'manual' && (
                  <IonButton
                    disabled={!puedeSerAutomatica(p)}
                    onClick={() =>
                      void ejecutar(
                        () => cambiarRevision(p.id, 'automatica'),
                        (x) => `${x.nombre} ya publica sin revisión.`,
                      )
                    }
                  >
                    ⚡ Pasar a publicar sin revisión
                  </IonButton>
                )}
                {p.estado === 'aprobado' && modoRevision(p) === 'automatica' && (
                  <IonButton
                    fill="outline"
                    color={deberiaVolverAManual(p) ? 'danger' : 'primary'}
                    onClick={() =>
                      void ejecutar(
                        () => cambiarRevision(p.id, 'manual'),
                        (x) => `Revisaremos a mano los planes de ${x.nombre}.`,
                      )
                    }
                  >
                    ✋ Pasar a revisión a mano
                  </IonButton>
                )}
              </div>
              {porAprobar(p) ? (
                <>
                  <div className="botones-decision">
                    <IonButton
                      color="success"
                      size="large"
                      onClick={() =>
                        void ejecutar(
                          () => aprobarPublicador(p.id, { aprobar: true }),
                          (x) => `${x.nombre} ya puede publicar, con revisión a mano.`,
                        )
                      }
                    >
                      ✔ Aprobar
                    </IonButton>
                    <IonButton
                      color="danger"
                      fill="outline"
                      size="large"
                      onClick={() =>
                        void ejecutar(
                          () => aprobarPublicador(p.id, { aprobar: false }),
                          (x) => `${x.nombre} rechazado.`,
                        )
                      }
                    >
                      ✖ Rechazar
                    </IonButton>
                  </div>
                </>
              ) : (
                (p.estado === 'aprobado' || p.estado === 'pausado') && (
                  <div className="controles-publicador">
                    <IonToggle
                      checked={!p.automatizaciones_pausadas}
                      disabled={p.estado === 'pausado'}
                      onIonChange={(ev) =>
                        void ejecutar(
                          () => pausarPublicador(p.id, { que: 'automatizaciones', pausado: !ev.detail.checked }),
                          (x) =>
                            x.automatizaciones_pausadas
                              ? `Ya no recogemos solos los planes de ${x.nombre}.`
                              : `Volvemos a recoger solos los planes de ${x.nombre}.`,
                        )
                      }
                    >
                      Recoger solos sus planes de redes y web
                    </IonToggle>
                    <IonButton
                      fill="outline"
                      color={p.estado === 'pausado' ? 'success' : 'danger'}
                      onClick={() =>
                        void ejecutar(
                          () => pausarPublicador(p.id, { que: 'publicador', pausado: p.estado !== 'pausado' }),
                          (x) =>
                            x.estado === 'pausado'
                              ? `${x.nombre} pausado: no puede publicar.`
                              : `${x.nombre} reactivado.`,
                        )
                      }
                    >
                      {p.estado === 'pausado' ? 'Reactivar' : 'Pausar'}
                    </IonButton>
                  </div>
                )
              )}
            </IonCardContent>
          </IonCard>
        ))}
      <IonToast isOpen={aviso != null} message={aviso ?? ''} duration={3000} onDidDismiss={() => setAviso(null)} />
    </PaginaAdmin>
  );
};

export default Publicadores;
