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
import { useEffect, useState } from 'react';

import { MUNICIPIOS, getChoques, type Choques } from '../api/client';
import {
  CATEGORIAS,
  PUBLICOS,
  type Categoria,
  type Evento,
  type EventoCrear,
  type Publicador,
  type Publico,
} from '../api/types';
import SelectorImagen from '../components/SelectorImagen';
import { useSesion } from '../cuenta/sesion';
import { claveDia, diaCorto, hora, isoMadrid } from '../utils/formato';

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
  // Plan nuevo: los mismos mínimos que «Proponer» de los vecinos (fin, público, responsable y teléfono) y los datos
  // que solo tiene el ayuntamiento (concejalía, espacio reservado, accesibilidad). Al editar no se piden.
  const nuevo = evento == null;
  const { usuario } = useSesion();
  const [horaFin, setHoraFin] = useState('');
  const [publico, setPublico] = useState<Publico>('todos');
  const [responsable, setResponsable] = useState(usuario?.nombre ?? '');
  const [telefono, setTelefono] = useState(usuario?.telefono ?? '');
  const [area, setArea] = useState('');
  const [espacioReservado, setEspacioReservado] = useState(false);
  const [accesible, setAccesible] = useState(false);
  // Choque de fechas: otro plan publicado ese día a 20 km o menos. Se avisa y se propone un día libre; decide quien
  // crea el plan.
  const claveChoque = nuevo && fecha && horaInicio ? `${isoMadrid(fecha, horaInicio)}|${municipio}` : null;
  const [revisado, setRevisado] = useState<{ clave: string; datos: Choques } | null>(null);
  useEffect(() => {
    if (!claveChoque) return;
    let vigente = true;
    const [iso, pueblo] = claveChoque.split('|');
    getChoques(iso, pueblo)
      .then((datos) => vigente && setRevisado({ clave: claveChoque, datos }))
      .catch(() => undefined);
    return () => {
      vigente = false;
    };
  }, [claveChoque]);
  const choque = revisado && revisado.clave === claveChoque && revisado.datos.choques.length ? revisado.datos : null;
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
    if (nuevo) {
      const faltan = [
        [lugar.trim(), 'el lugar'],
        [horaInicio, 'la hora de inicio'],
        [responsable.trim(), 'la persona responsable'],
        [telefono.trim(), 'un teléfono de contacto'],
        [gratis || Number(precioEur) > 0, 'el precio'],
      ]
        .filter(([ok]) => !ok)
        .map(([, t]) => t);
      if (faltan.length) return setError(`Falta ${faltan.join(', ')}.`);
      if (horaFin && horaFin <= horaInicio) return setError('La hora de fin tiene que ser después de la de inicio.');
    }
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
        ...(nuevo && {
          fecha_fin: horaFin ? isoMadrid(fecha, horaFin) : null,
          etiquetas: [`publico_${publico}`],
          datos_ayuntamiento: {
            responsable: responsable.trim(),
            telefono: telefono.trim(),
            entidad: 'ayuntamiento',
            publico,
            necesidades: [],
            seguro_rc: 'si',
            area: area.trim() || null,
            espacio_reservado: espacioReservado,
            accesible,
          },
        }),
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
        <IonToolbar color="secondary">
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
            {nuevo && (
              <IonInput
                label="Hora de fin (opcional)"
                labelPlacement="stacked"
                fill="outline"
                type="time"
                value={horaFin}
                onIonInput={(ev) => setHoraFin(ev.detail.value ?? '')}
              />
            )}
          </div>
          {choque && (
            <IonText color="warning">
              <div className="aviso-cambio" role="status">
                <p>
                  ⚠️ Ese día ya hay «{choque.choques[0].titulo}» en {choque.choques[0].municipio}. Si coinciden, puede
                  ir menos gente.
                </p>
                {choque.alternativas[0] && (
                  <IonButton size="small" fill="outline" onClick={() => setFecha(claveDia(choque.alternativas[0]))}>
                    📅 Cambiar al {diaCorto(choque.alternativas[0])}
                  </IonButton>
                )}
              </div>
            </IonText>
          )}
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
          {nuevo && (
            <>
              <IonSelect
                label="Para quién es"
                labelPlacement="stacked"
                fill="outline"
                value={publico}
                onIonChange={(ev) => setPublico(ev.detail.value as Publico)}
              >
                {(Object.keys(PUBLICOS) as Publico[]).map((k) => (
                  <IonSelectOption key={k} value={k}>
                    {PUBLICOS[k]}
                  </IonSelectOption>
                ))}
              </IonSelect>
              <div className="fila-form">
                <IonInput
                  label="Persona responsable"
                  labelPlacement="stacked"
                  fill="outline"
                  value={responsable}
                  maxlength={120}
                  onIonInput={(ev) => setResponsable(ev.detail.value ?? '')}
                />
                <IonInput
                  label="Teléfono de contacto"
                  labelPlacement="stacked"
                  fill="outline"
                  type="tel"
                  value={telefono}
                  maxlength={20}
                  onIonInput={(ev) => setTelefono(ev.detail.value ?? '')}
                />
              </div>
              <h3 className="titulo-caja">Datos del ayuntamiento</h3>
              <IonInput
                label="Concejalía o área que lo organiza (opcional)"
                labelPlacement="stacked"
                fill="outline"
                placeholder="Cultura, Deportes, Fiestas…"
                value={area}
                maxlength={120}
                onIonInput={(ev) => setArea(ev.detail.value ?? '')}
              />
              <IonToggle checked={espacioReservado} onIonChange={(ev) => setEspacioReservado(ev.detail.checked)}>
                El espacio municipal ya está reservado
              </IonToggle>
              <IonToggle checked={accesible} onIonChange={(ev) => setAccesible(ev.detail.checked)}>
                Accesible para personas con movilidad reducida
              </IonToggle>
            </>
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
