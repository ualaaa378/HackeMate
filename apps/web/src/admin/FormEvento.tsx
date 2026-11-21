import {
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonInput,
  IonModal,
  IonSelect,
  IonSelectOption,
  IonText,
  IonTextarea,
  IonTitle,
  IonToggle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';

import { MUNICIPIOS } from '../api/client';
import { CATEGORIAS, type Categoria, type Evento, type EventoCrear, type Publicador } from '../api/types';
import SelectorImagen from '../components/SelectorImagen';
import { claveDia, hora, isoMadrid } from '../utils/formato';

interface Props {
  abierto: boolean;
  /** null para crear uno nuevo. */
  evento: Evento | null;
  /** Solo el moderador elige publicador; el publicador publica siempre a su nombre. */
  publicadores: Publicador[];
  publicadorFijo: string | null;
  onGuardar: (datos: EventoCrear) => Promise<void>;
  onCancelarPlan?: () => Promise<void>;
  onCerrar: () => void;
}

const FormEvento: React.FC<Props> = (props) => (
  <IonModal isOpen={props.abierto} onDidDismiss={props.onCerrar}>
    {/* key: el formulario se monta de nuevo con los datos de cada evento */}
    {props.abierto && <Formulario key={props.evento?.id ?? 'nuevo'} {...props} />}
  </IonModal>
);

const Formulario: React.FC<Props> = ({ evento, publicadores, publicadorFijo, onGuardar, onCancelarPlan, onCerrar }) => {
  const [titulo, setTitulo] = useState(evento?.titulo ?? '');
  const [categoria, setCategoria] = useState<Categoria>(evento?.categoria ?? 'cultural');
  const [municipio, setMunicipio] = useState(evento?.municipio ?? MUNICIPIOS[0]);
  const [lugar, setLugar] = useState(evento?.lugar ?? '');
  const [fecha, setFecha] = useState(evento ? claveDia(evento.fecha_inicio) : '');
  const [horaInicio, setHoraInicio] = useState(evento ? hora(evento.fecha_inicio) : '18:00');
  const [gratis, setGratis] = useState(evento?.es_gratuito ?? true);
  const [precioEur, setPrecioEur] = useState(evento?.precio_eur != null ? String(evento.precio_eur) : '');
  const [plazasTotales, setPlazasTotales] = useState(
    evento?.plazas_totales != null ? String(evento.plazas_totales) : '',
  );
  const [descripcion, setDescripcion] = useState(evento?.descripcion ?? '');
  const [imagen, setImagen] = useState<string | null>(evento?.imagen_url ?? null);
  const [publicadorId, setPublicadorId] = useState<string | null>(publicadorFijo ?? evento?.publicador_id ?? null);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const cambiaHora =
    evento != null &&
    fecha !== '' &&
    isoMadrid(fecha, horaInicio) !== isoMadrid(claveDia(evento.fecha_inicio), hora(evento.fecha_inicio));
  const apuntados = evento?.inscritos ?? 0;

  const guardar = async () => {
    if (titulo.trim().length < 3) return setError('Escribe un nombre para el plan (mínimo 3 letras).');
    if (!fecha) return setError('Elige el día del plan.');
    setError(null);
    setGuardando(true);
    try {
      await onGuardar({
        titulo: titulo.trim(),
        categoria,
        municipio,
        lugar: lugar.trim() || null,
        fecha_inicio: isoMadrid(fecha, horaInicio),
        es_gratuito: gratis,
        precio_eur: gratis ? null : Number(precioEur) || null,
        plazas_totales: plazasTotales ? Number(plazasTotales) : null,
        descripcion: descripcion.trim(),
        imagen_url: imagen,
        publicador_id: publicadorId,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido guardar.');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <>
      <IonHeader>
        <IonToolbar color="primary">
          <IonTitle>{evento ? 'Editar plan' : 'Nuevo plan'}</IonTitle>
          <IonButtons slot="end">
            <IonButton onClick={onCerrar}>Cerrar</IonButton>
          </IonButtons>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        <form
          className="form-cuenta"
          onSubmit={(ev) => {
            ev.preventDefault();
            void guardar();
          }}
        >
          <IonInput
            label="Nombre del plan"
            labelPlacement="stacked"
            fill="outline"
            value={titulo}
            maxlength={120}
            onIonInput={(ev) => setTitulo(ev.detail.value ?? '')}
          />
          <IonSelect
            label="Tipo de plan"
            labelPlacement="stacked"
            fill="outline"
            value={categoria}
            onIonChange={(ev) => setCategoria(ev.detail.value as Categoria)}
          >
            {(Object.keys(CATEGORIAS) as Categoria[]).map((c) => (
              <IonSelectOption key={c} value={c}>
                {CATEGORIAS[c].emoji} {CATEGORIAS[c].etiqueta}
              </IonSelectOption>
            ))}
          </IonSelect>
          <IonSelect
            label="Pueblo"
            labelPlacement="stacked"
            fill="outline"
            value={municipio}
            disabled={evento != null}
            onIonChange={(ev) => setMunicipio(ev.detail.value as string)}
          >
            {MUNICIPIOS.map((m) => (
              <IonSelectOption key={m} value={m}>
                {m}
              </IonSelectOption>
            ))}
          </IonSelect>
          <IonInput
            label="Lugar (plaza, salón, ermita…)"
            labelPlacement="stacked"
            fill="outline"
            value={lugar}
            onIonInput={(ev) => setLugar(ev.detail.value ?? '')}
          />
          <div className="fila-form">
            <IonInput
              label="Día"
              labelPlacement="stacked"
              fill="outline"
              type="date"
              value={fecha}
              onIonInput={(ev) => setFecha(ev.detail.value ?? '')}
            />
            <IonInput
              label="Hora"
              labelPlacement="stacked"
              fill="outline"
              type="time"
              value={horaInicio}
              onIonInput={(ev) => setHoraInicio(ev.detail.value || '18:00')}
            />
          </div>
          {cambiaHora && apuntados > 0 && (
            <IonText color="warning">
              <p className="aviso-cambio">
                ⚠️ Hay {apuntados} {apuntados === 1 ? 'persona apuntada' : 'personas apuntadas'}. Al guardar les
                avisaremos del cambio por mensaje y saldrá un aviso fijo en la ficha.
              </p>
            </IonText>
          )}
          <IonToggle checked={gratis} onIonChange={(ev) => setGratis(ev.detail.checked)}>
            Es gratis
          </IonToggle>
          {!gratis && (
            <IonInput
              label="Precio en euros"
              labelPlacement="stacked"
              fill="outline"
              type="number"
              min="0"
              value={precioEur}
              onIonInput={(ev) => setPrecioEur(ev.detail.value ?? '')}
            />
          )}
          <IonInput
            label="Plazas (vacío si no hay límite)"
            labelPlacement="stacked"
            fill="outline"
            type="number"
            min="0"
            value={plazasTotales}
            onIonInput={(ev) => setPlazasTotales(ev.detail.value ?? '')}
          />
          {!publicadorFijo && (
            <IonSelect
              label="Quién lo organiza"
              labelPlacement="stacked"
              fill="outline"
              value={publicadorId ?? ''}
              onIonChange={(ev) => setPublicadorId((ev.detail.value as string) || null)}
            >
              <IonSelectOption value="">El ayuntamiento</IonSelectOption>
              {publicadores
                .filter((p) => p.estado === 'aprobado')
                .map((p) => (
                  <IonSelectOption key={p.id} value={p.id}>
                    {p.nombre}
                  </IonSelectOption>
                ))}
            </IonSelect>
          )}
          <IonTextarea
            label="Descripción"
            labelPlacement="stacked"
            fill="outline"
            autoGrow
            rows={4}
            value={descripcion}
            onIonInput={(ev) => setDescripcion(ev.detail.value ?? '')}
          />
          <SelectorImagen valor={imagen} onCambio={setImagen} />
          {error && (
            <IonText color="danger">
              <p className="error-form" role="alert">
                {error}
              </p>
            </IonText>
          )}
          <IonButton type="submit" expand="block" size="large" disabled={guardando}>
            {evento ? 'Guardar cambios' : 'Publicar plan'}
          </IonButton>
          {evento && onCancelarPlan && evento.estado === 'publicado' && (
            <IonButton
              expand="block"
              color="danger"
              fill="outline"
              disabled={guardando}
              onClick={() => void onCancelarPlan()}
            >
              Cancelar este plan
            </IonButton>
          )}
        </form>
      </IonContent>
    </>
  );
};

export default FormEvento;
