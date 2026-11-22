import {
  IonAlert,
  IonBackButton,
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonContent,
  IonHeader,
  IonPage,
  IonSpinner,
  IonText,
  IonTitle,
  IonToast,
  IonToolbar,
  useIonViewWillEnter,
} from '@ionic/react';
import { useCallback, useState } from 'react';

import FormEvento from '../admin/FormEvento';
import { apelarPlan, ErrorApi, getMisPlanes, modificarPlan } from '../api/client';
import { CATEGORIAS, type Evento, type EventoCrear } from '../api/types';
import { useSesion } from '../cuenta/sesion';
import { imagenPlan } from '../eventos/imagenes';
import { estadoPlan, MOTIVO_APELACION, puedeApelar } from '../utils/estadoPlan';
import { fechaLarga, horaEvento, textoApuntados } from '../utils/formato';

/** P5c · «Mis planes propuestos»: lo que ha propuesto esta persona (o su asociación), con su estado, y «Modificar». */
const MisPlanes: React.FC = () => {
  const { usuario, abrirCuenta } = useSesion();
  const [planes, setPlanes] = useState<Evento[] | null>(null);
  const [error, setError] = useState(false);
  const [editando, setEditando] = useState<Evento | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [apelando, setApelando] = useState<Evento | null>(null);
  const usuarioId = usuario?.id;

  const cargar = useCallback(() => {
    if (!usuarioId) return;
    getMisPlanes(usuarioId)
      .then((lista) => {
        setPlanes(lista);
        setError(false);
      })
      .catch(() => setError(true));
  }, [usuarioId]);

  useIonViewWillEnter(cargar, [cargar]);

  const guardar = async (datos: EventoCrear) => {
    if (!editando) return;
    const { municipio: _m, publicador_id: _p, ...cambios } = datos;
    const cambioHora = editando.fecha_inicio !== datos.fecha_inicio && (editando.inscritos ?? 0) > 0;
    const nuevo = await modificarPlan(editando.id, cambios);
    setPlanes((l) => l?.map((e) => (e.id === nuevo.id ? { ...e, ...nuevo } : e)) ?? null);
    setAviso(
      cambioHora
        ? `Guardado. Avisamos del cambio de hora a ${textoApuntados(editando).toLowerCase()}.`
        : 'Cambios guardados.',
    );
    setEditando(null);
  };

  const cancelar = async () => {
    if (!editando) return;
    const nuevo = await modificarPlan(editando.id, { estado: 'cancelado' });
    setPlanes((l) => l?.map((e) => (e.id === nuevo.id ? { ...e, ...nuevo } : e)) ?? null);
    setAviso('Plan cancelado. Avisamos a quien estaba apuntado.');
    setEditando(null);
  };

  // P3c: devuelve false para dejar el cuadro abierto si el motivo es demasiado corto.
  const apelar = (motivo: string): boolean => {
    const plan = apelando;
    const texto = motivo.trim();
    if (!plan) return true;
    if (texto.length < MOTIVO_APELACION.min) {
      setAviso(`Cuéntanos un poco más (al menos ${MOTIVO_APELACION.min} letras).`);
      return false;
    }
    apelarPlan(plan.id, texto.slice(0, MOTIVO_APELACION.max))
      .then((nuevo) => {
        setPlanes((l) => l?.map((e) => (e.id === nuevo.id ? { ...e, ...nuevo } : e)) ?? null);
        setAviso('Enviado. El ayuntamiento lo revisará otra vez.');
      })
      .catch((err: unknown) => {
        const codigo = err instanceof ErrorApi ? err.code : '';
        setAviso(
          codigo === 'apelacion_usada'
            ? 'Ya pediste que lo revisaran. Esta segunda decisión es definitiva.'
            : codigo === 'estado_invalido'
              ? 'Este plan ya no está rechazado. Recarga la página.'
              : 'No hemos podido enviarlo. Inténtalo de nuevo en un momento.',
        );
      });
    return true;
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <IonBackButton defaultHref="/perfil" text="Volver" />
          </IonButtons>
          <IonTitle>📝 Mis planes propuestos</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding contenido-lectura">
        {!usuario ? (
          <IonCard>
            <IonCardContent>
              <p>Entra con tu cuenta para ver los planes que has propuesto y cambiarlos.</p>
              <IonButton expand="block" onClick={abrirCuenta}>
                Crear cuenta o entrar
              </IonButton>
            </IonCardContent>
          </IonCard>
        ) : error ? (
          <IonText color="danger">
            <p role="alert">No hemos podido cargar tus planes. Inténtalo de nuevo en un momento.</p>
          </IonText>
        ) : !planes ? (
          <div className="centrado">
            <IonSpinner aria-label="Cargando" />
          </div>
        ) : planes.length === 0 ? (
          <IonCard>
            <IonCardContent>
              <p>
                Todavía no has propuesto ningún plan. Cuando lo hagas, aquí verás si el ayuntamiento lo ha publicado.
              </p>
              <IonButton expand="block" routerLink="/proponer">
                Proponer un plan
              </IonButton>
            </IonCardContent>
          </IonCard>
        ) : (
          <>
            <p className="nota-demo">
              Aquí ves en qué punto está cada plan. Si cambias la hora de uno publicado, avisamos a quien se apuntó.
            </p>
            <ul className="mis-planes">
              {planes.map((e) => {
                const est = estadoPlan(e);
                const img = imagenPlan(e);
                const motivo = e.moderacion?.motivo;
                return (
                  <li key={e.id} className={`mi-plan mi-plan--${est.clase}`}>
                    <img src={img.miniatura} alt="" loading="lazy" decoding="async" />
                    <div className="mi-plan__texto">
                      <span className={`mi-plan__estado mi-plan__estado--${est.clase}`}>{est.texto}</span>
                      <strong>{e.titulo}</strong>
                      <span>
                        {CATEGORIAS[e.categoria].emoji} {fechaLarga(e.fecha_inicio)} · {horaEvento(e)}
                      </span>
                      <span>📍 {e.municipio}</span>
                      {(est.clase === 'publicado' || est.clase === 'hecho') && <span>👥 {textoApuntados(e)}</span>}
                      {est.clase === 'rechazado' && motivo && <span className="mi-plan__motivo">Motivo: {motivo}</span>}
                      {est.clase === 'rechazado' && e.apelacion && (
                        <span>Ya pediste que lo revisaran otra vez. Esta decisión es definitiva.</span>
                      )}
                      <div className="mi-plan__botones">
                        {est.modificable && (
                          <IonButton size="small" onClick={() => setEditando(e)}>
                            Modificar
                          </IonButton>
                        )}
                        {puedeApelar(e) && (
                          <IonButton size="small" onClick={() => setApelando(e)}>
                            🔁 Pedir que lo revisen otra vez
                          </IonButton>
                        )}
                        {(est.clase === 'publicado' || est.clase === 'hecho') && (
                          <IonButton size="small" fill="outline" routerLink={`/evento/${e.id}`}>
                            Ver ficha
                          </IonButton>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
        <FormEvento
          abierto={!!editando}
          evento={editando}
          publicadores={[]}
          publicadorFijo={editando?.publicador_id ?? null}
          onGuardar={guardar}
          onCancelarPlan={cancelar}
          onCerrar={() => setEditando(null)}
        />
        <IonAlert
          isOpen={!!apelando}
          onDidDismiss={() => setApelando(null)}
          header="Pedir que lo revisen otra vez"
          message="Cuéntale al ayuntamiento por qué debería publicarse. Solo se puede pedir una vez."
          inputs={[
            {
              name: 'motivo',
              type: 'textarea',
              placeholder: 'Por ejemplo: es la fiesta del pueblo de todos los años y ya tenemos permiso',
              attributes: { maxlength: MOTIVO_APELACION.max, 'aria-label': 'Por qué debería publicarse' },
            },
          ]}
          buttons={[
            { text: 'Cancelar', role: 'cancel' },
            { text: 'Enviar', handler: (datos: { motivo?: string }) => apelar(datos.motivo ?? '') },
          ]}
        />
        <IonToast isOpen={!!aviso} message={aviso ?? ''} duration={3000} onDidDismiss={() => setAviso(null)} />
      </IonContent>
    </IonPage>
  );
};

export default MisPlanes;
