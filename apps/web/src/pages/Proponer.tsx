import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonCheckbox,
  IonContent,
  IonHeader,
  IonInput,
  IonPage,
  IonSegment,
  IonSegmentButton,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonText,
  IonTextarea,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';

import { MUNICIPIOS, ErrorApi, proponerEvento, type PropuestaEnviada } from '../api/client';
import {
  CATEGORIAS,
  NECESIDADES,
  PUBLICOS,
  type Categoria,
  type DatosAyuntamiento,
  type Necesidad,
  type Publico,
} from '../api/types';
import SelectorImagen from '../components/SelectorImagen';
import { useSesion } from '../cuenta/sesion';
import { fechaLarga } from '../utils/formato';

const ENTIDADES: Record<DatosAyuntamiento['entidad'], string> = {
  particular: 'Vecino o vecina',
  asociacion: 'Asociación o peña',
  comercio: 'Comercio o empresa',
  otra: 'Otra entidad',
};

/** Hora de Madrid en noviembre–marzo (+01:00) o el resto del año (+02:00), suficiente para la demo. */
function isoMadrid(dia: string, hora: string): string {
  const mes = Number(dia.slice(5, 7));
  const zona = mes >= 4 && mes <= 10 ? '+02:00' : '+01:00';
  return `${dia}T${hora}:00${zona}`;
}

const Proponer: React.FC = () => {
  const { usuario, conCuenta } = useSesion();
  const [f, setF] = useState({
    titulo: '',
    categoria: 'cultural' as Categoria,
    municipio: MUNICIPIOS[0],
    descripcion: '',
    dia: '',
    hora: '',
    fin: '',
    lugar: '',
    publico: 'todos' as Publico,
    plazas: '',
    pago: 'no' as 'si' | 'no',
    precio: '',
    responsable: usuario?.nombre ?? '',
    telefono: usuario?.telefono ?? '',
    entidad: 'particular' as DatosAyuntamiento['entidad'],
    entidad_nombre: '',
    necesidades: [] as Necesidad[],
    seguro_rc: 'nose' as DatosAyuntamiento['seguro_rc'],
    observaciones: '',
    imagen: null as string | null,
    frase: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [enviada, setEnviada] = useState<PropuestaEnviada | null>(null);

  const poner = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const texto = (k: keyof typeof f) => (e: { detail: { value?: string | null } }) =>
    poner(k, (e.detail.value ?? '') as never);

  const enviar = (ev: React.FormEvent) => {
    ev.preventDefault();
    const faltan = [
      [f.titulo.trim().length >= 3, 'el nombre del plan'],
      [f.dia, 'el día'],
      [f.hora, 'la hora de inicio'],
      [f.lugar.trim(), 'el lugar'],
      [f.responsable.trim(), 'la persona responsable'],
      [f.telefono.trim(), 'un teléfono de contacto'],
      [f.pago === 'no' || f.precio, 'el precio'],
    ]
      .filter(([ok]) => !ok)
      .map(([, t]) => t);
    if (faltan.length) return setError(`Falta ${faltan.join(', ')}.`);
    setError(null);
    conCuenta('Para proponer un plan necesitas una cuenta. Así el ayuntamiento puede contactarte.', async () => {
      setEnviando(true);
      try {
        const r = await proponerEvento(
          {
            titulo: f.titulo.trim(),
            descripcion: f.descripcion.trim() || undefined,
            categoria: f.categoria,
            municipio: f.municipio,
            lugar: f.lugar.trim(),
            fecha_inicio: isoMadrid(f.dia, f.hora),
            fecha_fin: f.fin ? isoMadrid(f.dia, f.fin) : null,
            es_gratuito: f.pago === 'no',
            precio_eur: f.pago === 'si' ? Number(f.precio) : null,
            plazas_totales: f.plazas ? Number(f.plazas) : null,
            etiquetas: ['propuesta_vecinal', `publico_${f.publico}`],
            imagen_url: f.imagen,
          },
          {
            responsable: f.responsable.trim(),
            telefono: f.telefono.trim(),
            entidad: f.entidad,
            entidad_nombre: f.entidad_nombre.trim() || undefined,
            publico: f.publico,
            necesidades: f.necesidades,
            seguro_rc: f.seguro_rc,
            observaciones: f.observaciones.trim() || undefined,
            frase_portada: f.frase.trim() || undefined,
          },
        );
        setEnviada(r);
      } catch (e) {
        setError(e instanceof ErrorApi ? e.message : 'No hemos podido enviar la propuesta. Inténtalo de nuevo.');
      } finally {
        setEnviando(false);
      }
    });
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <IonBackButton defaultHref="/agenda" text="Volver" />
          </IonButtons>
          <IonTitle>Proponer un plan</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding contenido-lectura">
        {enviada ? (
          <IonCard className="propuesta-ok">
            <IonCardContent>
              <h2 className="titulo-caja">✅ Propuesta enviada</h2>
              <p>
                El Ayuntamiento de {enviada.evento.municipio} ya tiene tu propuesta «{enviada.evento.titulo}» para el{' '}
                {fechaLarga(enviada.evento.fecha_inicio)}. Te escribiremos cuando la revisen.
              </p>
              <p className="nota">
                Estado: en revisión.{enviada.demo && ' (Modo demo: aún no se guarda en el servidor).'}
              </p>
              <IonButton expand="block" routerLink="/agenda">
                Volver a la agenda
              </IonButton>
            </IonCardContent>
          </IonCard>
        ) : (
          <form className="form-propuesta" onSubmit={enviar} noValidate>
            <p className="motivo">
              Cuéntanos tu idea. El ayuntamiento la revisa, te contacta si hace falta algún permiso y, si la aprueba,
              sale en la agenda.
            </p>

            <fieldset>
              <legend>El plan</legend>
              <IonInput
                label="Nombre del plan"
                labelPlacement="stacked"
                fill="outline"
                placeholder="Ej.: Ruta al Castillo de Tahal"
                value={f.titulo}
                onIonInput={texto('titulo')}
              />
              <IonSelect
                label="Tipo de plan"
                labelPlacement="stacked"
                fill="outline"
                interface="action-sheet"
                cancelText="Cancelar"
                value={f.categoria}
                onIonChange={(e) => poner('categoria', e.detail.value)}
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
                interface="action-sheet"
                cancelText="Cancelar"
                value={f.municipio}
                onIonChange={(e) => poner('municipio', e.detail.value)}
              >
                {MUNICIPIOS.map((m) => (
                  <IonSelectOption key={m} value={m}>
                    {m}
                  </IonSelectOption>
                ))}
              </IonSelect>
              <IonTextarea
                label="¿En qué consiste?"
                labelPlacement="stacked"
                fill="outline"
                autoGrow
                rows={3}
                placeholder="Qué se hará, qué hay que llevar…"
                value={f.descripcion}
                onIonInput={texto('descripcion')}
              />
              <SelectorImagen valor={f.imagen} onCambio={(v) => poner('imagen', v)} />
              <IonInput
                label="Frase para la portada (opcional)"
                labelPlacement="stacked"
                fill="outline"
                maxlength={90}
                counter
                placeholder="Ej.: ¡Trae a tu vecina, que esto no se repite!"
                value={f.frase}
                onIonInput={texto('frase')}
                helperText="Sale bajo la foto en Inicio. Si la dejas vacía, ponemos una frase automática."
              />
            </fieldset>

            <fieldset>
              <legend>Cuándo y dónde</legend>
              <IonInput
                label="Día"
                labelPlacement="stacked"
                fill="outline"
                type="date"
                value={f.dia}
                onIonInput={texto('dia')}
              />
              <div className="fila-2">
                <IonInput
                  label="Hora de inicio"
                  labelPlacement="stacked"
                  fill="outline"
                  type="time"
                  value={f.hora}
                  onIonInput={texto('hora')}
                />
                <IonInput
                  label="Hora de fin (aprox.)"
                  labelPlacement="stacked"
                  fill="outline"
                  type="time"
                  value={f.fin}
                  onIonInput={texto('fin')}
                />
              </div>
              <IonInput
                label="Lugar"
                labelPlacement="stacked"
                fill="outline"
                placeholder="Ej.: Plaza de la Iglesia"
                value={f.lugar}
                onIonInput={texto('lugar')}
              />
            </fieldset>

            <fieldset>
              <legend>Quién puede ir</legend>
              <IonSelect
                label="Público"
                labelPlacement="stacked"
                fill="outline"
                interface="action-sheet"
                cancelText="Cancelar"
                value={f.publico}
                onIonChange={(e) => poner('publico', e.detail.value)}
              >
                {(Object.keys(PUBLICOS) as Publico[]).map((p) => (
                  <IonSelectOption key={p} value={p}>
                    {PUBLICOS[p]}
                  </IonSelectOption>
                ))}
              </IonSelect>
              <IonInput
                label="Plazas aproximadas (vacío si no hay límite)"
                labelPlacement="stacked"
                fill="outline"
                type="number"
                inputmode="numeric"
                min="1"
                value={f.plazas}
                onIonInput={texto('plazas')}
              />
              <span className="etq" id="e-pago">
                ¿Es de pago?
              </span>
              <IonSegment
                aria-labelledby="e-pago"
                value={f.pago}
                onIonChange={(e) => poner('pago', e.detail.value as 'si' | 'no')}
              >
                <IonSegmentButton value="no">Gratis</IonSegmentButton>
                <IonSegmentButton value="si">De pago</IonSegmentButton>
              </IonSegment>
              {f.pago === 'si' && (
                <IonInput
                  label="Precio por persona (€)"
                  labelPlacement="stacked"
                  fill="outline"
                  type="number"
                  inputmode="decimal"
                  min="0"
                  step="0.5"
                  value={f.precio}
                  onIonInput={texto('precio')}
                />
              )}
            </fieldset>

            <fieldset>
              <legend>Responsable</legend>
              <IonInput
                label="Persona responsable"
                labelPlacement="stacked"
                fill="outline"
                autocomplete="name"
                value={f.responsable}
                onIonInput={texto('responsable')}
              />
              <IonInput
                label="Teléfono de contacto (no se publica)"
                labelPlacement="stacked"
                fill="outline"
                type="tel"
                inputmode="tel"
                autocomplete="tel"
                value={f.telefono}
                onIonInput={texto('telefono')}
              />
              <IonSelect
                label="Propone"
                labelPlacement="stacked"
                fill="outline"
                interface="action-sheet"
                cancelText="Cancelar"
                value={f.entidad}
                onIonChange={(e) => poner('entidad', e.detail.value)}
              >
                {Object.entries(ENTIDADES).map(([k, t]) => (
                  <IonSelectOption key={k} value={k}>
                    {t}
                  </IonSelectOption>
                ))}
              </IonSelect>
              {f.entidad !== 'particular' && (
                <IonInput
                  label="Nombre de la entidad"
                  labelPlacement="stacked"
                  fill="outline"
                  value={f.entidad_nombre}
                  onIonInput={texto('entidad_nombre')}
                />
              )}
            </fieldset>

            <fieldset>
              <legend>Lo que necesita el ayuntamiento</legend>
              <span className="etq">¿Qué vais a necesitar?</span>
              {(Object.keys(NECESIDADES) as Necesidad[]).map((n) => (
                <IonCheckbox
                  key={n}
                  labelPlacement="end"
                  justify="start"
                  checked={f.necesidades.includes(n)}
                  onIonChange={(e) =>
                    poner(
                      'necesidades',
                      e.detail.checked ? [...f.necesidades, n] : f.necesidades.filter((x) => x !== n),
                    )
                  }
                >
                  <span className="ion-text-wrap">{NECESIDADES[n]}</span>
                </IonCheckbox>
              ))}
              <span className="etq" id="e-seguro">
                ¿Tenéis seguro de responsabilidad civil?
              </span>
              <IonSegment
                aria-labelledby="e-seguro"
                value={f.seguro_rc}
                onIonChange={(e) => poner('seguro_rc', e.detail.value as DatosAyuntamiento['seguro_rc'])}
              >
                <IonSegmentButton value="si">Sí</IonSegmentButton>
                <IonSegmentButton value="no">No</IonSegmentButton>
                <IonSegmentButton value="nose">No lo sé</IonSegmentButton>
              </IonSegment>
              <IonTextarea
                label="Otras observaciones para el ayuntamiento"
                labelPlacement="stacked"
                fill="outline"
                autoGrow
                rows={3}
                placeholder="Accesibilidad, aparcamiento, si se repite cada año…"
                value={f.observaciones}
                onIonInput={texto('observaciones')}
              />
            </fieldset>

            {error && (
              <IonText color="danger" role="alert">
                <p className="error-form">{error}</p>
              </IonText>
            )}
            <IonButton type="submit" expand="block" size="large" disabled={enviando}>
              {enviando ? <IonSpinner name="dots" /> : 'Enviar propuesta al ayuntamiento'}
            </IonButton>
          </form>
        )}
      </IonContent>
    </IonPage>
  );
};

export default Proponer;
