import {
  IonBadge,
  IonButton,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardSubtitle,
  IonCardTitle,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonToast,
  IonToggle,
} from '@ionic/react';
import { useEffect, useState } from 'react';

import PaginaAdmin from '../../admin/PaginaAdmin';
import { aprobarPublicador, getPublicadores, pausarPublicador } from '../../api/admin';
import type { Publicador } from '../../api/types';

const TIPOS: Record<Publicador['tipo'], string> = {
  asociacion: 'Asociación',
  ayuntamiento: 'Ayuntamiento',
  bar_restaurante: 'Bar o restaurante',
  comercio: 'Comercio',
  otro: 'Otro',
};

const ESTADOS: Record<Publicador['estado'], { texto: string; color: string }> = {
  solicitado: { texto: 'Ha pedido acceso', color: 'warning' },
  whatsapp_verificado: { texto: 'Por aprobar', color: 'warning' },
  aprobado: { texto: 'Activo', color: 'success' },
  rechazado: { texto: 'Rechazado', color: 'medium' },
  pausado: { texto: 'Pausado', color: 'danger' },
};

const NIVELES = {
  0: 'Nivel 0 · se revisa todo',
  1: 'Nivel 1 · se revisa a mano',
  2: 'Nivel 2 · publica directo',
} as const;

const Publicadores: React.FC = () => {
  const [lista, setLista] = useState<Publicador[] | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [nivelNuevo, setNivelNuevo] = useState<Record<string, 0 | 1 | 2>>({});

  useEffect(() => {
    getPublicadores()
      .then((p) => setLista(p.items))
      .catch(() => setLista([]));
  }, []);

  const reemplazar = (p: Publicador) => setLista((xs) => xs?.map((x) => (x.id === p.id ? p : x)) ?? null);

  const ejecutar = async (accion: () => Promise<Publicador>, texto: (p: Publicador) => string) => {
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
    <PaginaAdmin titulo="🤝 Asociaciones" roles={['moderador']}>
      <p className="intro-admin">
        Quién puede publicar planes. Cuantos más planes aprobados, más sube su nivel de confianza.
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
                <IonBadge color="light">{NIVELES[p.nivel_confianza]}</IonBadge>
              </div>
              <IonCardTitle>{p.nombre}</IonCardTitle>
              <IonCardSubtitle>
                {TIPOS[p.tipo]} · 📍 {p.municipio}
                {p.aprobaciones != null && ` · ${p.aprobaciones} planes aprobados`}
              </IonCardSubtitle>
            </IonCardHeader>
            <IonCardContent>
              {p.descripcion && <p>{p.descripcion}</p>}
              {p.fuentes && p.fuentes.length > 0 && (
                <p className="fuentes">
                  Vigilamos: {p.fuentes.map((f) => f.url.replace(/^https?:\/\/(www\.)?/, '')).join(', ')}
                </p>
              )}

              {porAprobar(p) ? (
                <>
                  <IonSelect
                    label="Nivel de confianza al aprobar"
                    labelPlacement="stacked"
                    fill="outline"
                    value={nivelNuevo[p.id] ?? 0}
                    onIonChange={(ev) => setNivelNuevo((n) => ({ ...n, [p.id]: ev.detail.value as 0 | 1 | 2 }))}
                  >
                    {([0, 1, 2] as const).map((n) => (
                      <IonSelectOption key={n} value={n}>
                        {NIVELES[n]}
                      </IonSelectOption>
                    ))}
                  </IonSelect>
                  <div className="botones-decision">
                    <IonButton
                      color="success"
                      size="large"
                      onClick={() =>
                        void ejecutar(
                          () => aprobarPublicador(p.id, { aprobar: true, nivel_confianza: nivelNuevo[p.id] ?? 0 }),
                          (x) => `${x.nombre} ya puede publicar.`,
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
                              ? `Ya no importamos solos los planes de ${x.nombre}.`
                              : `Volvemos a importar los planes de ${x.nombre}.`,
                        )
                      }
                    >
                      Importar sus planes automáticamente
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
