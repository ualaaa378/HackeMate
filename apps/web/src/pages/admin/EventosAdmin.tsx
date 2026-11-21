import {
  IonBadge,
  IonButton,
  IonIcon,
  IonItem,
  IonLabel,
  IonList,
  IonSegment,
  IonSegmentButton,
  IonSpinner,
  IonToast,
} from '@ionic/react';
import { add, arrowUndo } from 'ionicons/icons';
import { useCallback, useEffect, useState } from 'react';

import FormEvento from '../../admin/FormEvento';
import PaginaAdmin from '../../admin/PaginaAdmin';
import { useAcceso } from '../../admin/acceso';
import { crearEvento, decidir, editarEvento, getEventosAdmin, getPublicadores } from '../../api/admin';
import { CATEGORIAS, type EstadoEvento, type Evento, type EventoCrear, type Publicador } from '../../api/types';
import { fechaLarga, horaEvento, textoApuntados } from '../../utils/formato';

const PESTANAS: { valor: EstadoEvento; texto: string }[] = [
  { valor: 'publicado', texto: 'Publicados' },
  { valor: 'en_revision', texto: 'En revisión' },
  { valor: 'rechazado', texto: 'Rechazados' },
  { valor: 'cancelado', texto: 'Cancelados' },
];

const EventosAdmin: React.FC = () => {
  const { rol, publicadorId } = useAcceso();
  const [estado, setEstado] = useState<EstadoEvento>('publicado');
  const [eventos, setEventos] = useState<Evento[] | null>(null);
  const [publicadores, setPublicadores] = useState<Publicador[]>([]);
  const [editando, setEditando] = useState<Evento | null>(null);
  const [formAbierto, setFormAbierto] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(() => {
    if (!rol) return;
    getEventosAdmin({ estado, publicador_id: publicadorId ?? undefined })
      .then((p) => setEventos(p.items))
      .catch(() => setEventos([]));
  }, [estado, publicadorId, rol]);

  useEffect(cargar, [cargar]);
  useEffect(() => {
    if (rol === 'moderador')
      getPublicadores()
        .then((p) => setPublicadores(p.items))
        .catch(() => setPublicadores([]));
  }, [rol]);

  const abrir = (e: Evento | null) => {
    setEditando(e);
    setFormAbierto(true);
  };

  const guardar = async (datos: EventoCrear) => {
    if (editando) {
      const { municipio: _m, publicador_id: _p, ...cambios } = datos;
      const cambioHora = editando.fecha_inicio !== datos.fecha_inicio && (editando.inscritos ?? 0) > 0;
      await editarEvento(editando.id, cambios);
      setAviso(
        cambioHora
          ? `Guardado. Avisamos del cambio a ${textoApuntados(editando).toLowerCase()}.`
          : 'Cambios guardados.',
      );
    } else {
      const nuevo = await crearEvento(datos, { rol: rol ?? 'publicador' });
      setAviso(nuevo.estado === 'publicado' ? 'Publicado en la agenda.' : 'Enviado al ayuntamiento para revisar.');
    }
    setFormAbierto(false);
    cargar();
  };

  const restaurar = async (e: Evento) => {
    try {
      await decidir(e.id, { decision: 'restaurar' });
      setAviso(`«${e.titulo}» vuelve a la bandeja para revisarlo de nuevo.`);
    } catch {
      setAviso('No se ha podido restaurar. Prueba otra vez.');
    }
    cargar();
  };

  const cancelarPlan = async () => {
    if (!editando) return;
    await editarEvento(editando.id, { estado: 'cancelado' });
    setAviso('Plan cancelado. Avisamos a los apuntados.');
    setFormAbierto(false);
    cargar();
  };

  return (
    <PaginaAdmin
      titulo={rol === 'publicador' ? '📋 Mis planes' : '📋 Planes'}
      acciones={
        <IonButton onClick={() => abrir(null)}>
          <IonIcon slot="start" icon={add} aria-hidden="true" />
          Nuevo plan
        </IonButton>
      }
    >
      <IonSegment value={estado} onIonChange={(ev) => setEstado(ev.detail.value as EstadoEvento)} scrollable>
        {PESTANAS.map((p) => (
          <IonSegmentButton key={p.valor} value={p.valor}>
            <IonLabel>{p.texto}</IonLabel>
          </IonSegmentButton>
        ))}
      </IonSegment>

      {!eventos && (
        <div className="centrado">
          <IonSpinner aria-label="Cargando" />
        </div>
      )}
      {eventos?.length === 0 && <p className="vacio-admin">No hay planes en este estado.</p>}
      <IonList>
        {eventos?.map((e) => (
          <IonItem key={e.id} button detail lines="full" className="tarjeta-evento" onClick={() => abrir(e)}>
            <div
              slot="start"
              className="emoji-categoria"
              style={{ background: CATEGORIAS[e.categoria].color }}
              aria-hidden="true"
            >
              {CATEGORIAS[e.categoria].emoji}
            </div>
            <IonLabel>
              <h2>{e.titulo}</h2>
              <p>
                📅 {fechaLarga(e.fecha_inicio)} · 🕘 {horaEvento(e)} · 📍 {e.municipio}
              </p>
              <p>
                {e.publicador_nombre ?? 'Ayuntamiento'}
                {e.moderacion?.motivo && ` · Motivo: ${e.moderacion.motivo}`}
              </p>
            </IonLabel>
            {rol === 'moderador' && e.estado === 'rechazado' ? (
              <IonButton
                slot="end"
                fill="outline"
                onClick={(ev) => {
                  ev.stopPropagation();
                  void restaurar(e);
                }}
              >
                <IonIcon slot="start" icon={arrowUndo} aria-hidden="true" />
                Restaurar
              </IonButton>
            ) : (
              <IonBadge slot="end" color="light">
                👥 {e.inscritos ?? 0}
              </IonBadge>
            )}
          </IonItem>
        ))}
      </IonList>

      <FormEvento
        abierto={formAbierto}
        evento={editando}
        publicadores={publicadores}
        publicadorFijo={publicadorId}
        onGuardar={guardar}
        onCancelarPlan={cancelarPlan}
        onCerrar={() => setFormAbierto(false)}
      />
      <IonToast isOpen={aviso != null} message={aviso ?? ''} duration={3500} onDidDismiss={() => setAviso(null)} />
    </PaginaAdmin>
  );
};

export default EventosAdmin;
