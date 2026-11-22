import { IonButton, IonIcon, IonInput, IonSpinner } from '@ionic/react';
import { camera, close } from 'ionicons/icons';
import { useCallback, useEffect, useId, useRef, useState } from 'react';

import { enviarMensaje, getMensajes, meApunte } from '../api/client';
import type { Evento, MensajeEvento, Usuario } from '../api/types';
import { useSesion } from '../cuenta/sesion';
import { comprimirImagen } from '../utils/imagen';

/* Lo que queda de un plan que ya ha pasado: las fotos que han subido quienes fueron o la organización,
   y los comentarios, que se pueden seguir escribiendo después. No hay inscripción ni preguntas. */

function puedeSubirFotos(evento: Pick<Evento, 'id' | 'publicador_id'>, u: Usuario | null): boolean {
  if (!u) return false;
  if (u.rol === 'moderador') return true;
  if (u.publicador_id && u.publicador_id === evento.publicador_id) return true;
  return meApunte(evento.id);
}

interface Foto {
  id: string;
  src: string;
  autor: string;
}

const RecuerdoPlan: React.FC<{
  evento: Evento;
  /** Se llama con el número de comentarios cada vez que cambia la lista. */
  onTotal?: (total: number) => void;
}> = ({ evento, onTotal }) => {
  const { usuario, conCuenta } = useSesion();
  const idFoto = useId();
  const entrada = useRef<HTMLInputElement>(null);
  const [mensajes, setMensajes] = useState<MensajeEvento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [texto, setTexto] = useState('');
  const [foto, setFoto] = useState<string | null>(null);
  const [preparando, setPreparando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ampliada, setAmpliada] = useState<Foto | null>(null);

  const visibles = useCallback(
    (items: MensajeEvento[]) => items.filter((m) => m.tipo === 'comentario' && !m.oculto),
    [],
  );

  useEffect(() => {
    let vivo = true;
    getMensajes(evento.id)
      .then((p) => {
        if (!vivo) return;
        const lista = visibles(p.items);
        setMensajes(lista);
        onTotal?.(lista.length);
      })
      .catch(() => vivo && setError('No hemos podido cargar los comentarios.'))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, [evento.id, visibles, onTotal]);

  const fotos: Foto[] = [
    ...(evento.imagen_url
      ? [{ id: 'organizacion', src: evento.imagen_url, autor: evento.publicador_nombre ?? 'La organización' }]
      : []),
    ...mensajes.filter((m) => m.imagen_url).map((m) => ({ id: m.id, src: m.imagen_url!, autor: m.autor_nombre })),
  ];
  const conPermiso = puedeSubirFotos(evento, usuario);

  const elegirFoto = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = ev.target.files?.[0];
    ev.target.value = '';
    if (!archivo) return;
    if (!archivo.type.startsWith('image/')) return setError('Elige una foto (JPG, PNG o similar).');
    setError(null);
    setPreparando(true);
    try {
      setFoto(await comprimirImagen(archivo, 1000));
    } catch {
      setError('No hemos podido leer esa foto. Prueba con otra.');
    } finally {
      setPreparando(false);
    }
  };

  const publicar = (ev: React.FormEvent) => {
    ev.preventDefault();
    const t = texto.trim() || (foto ? '📷 Foto del plan' : '');
    if (!t) return;
    conCuenta('Para comentar un plan necesitas una cuenta. Así se sabe quién lo escribe.', async (u) => {
      setEnviando(true);
      setError(null);
      try {
        const subeFoto = foto && puedeSubirFotos(evento, u) ? foto : null;
        await enviarMensaje(evento.id, { texto: t, tipo: 'comentario', imagen_url: subeFoto }, u);
        setTexto('');
        setFoto(null);
        const lista = visibles((await getMensajes(evento.id)).items);
        setMensajes(lista);
        onTotal?.(lista.length);
      } catch {
        setError('No hemos podido publicar tu comentario. Inténtalo de nuevo.');
      } finally {
        setEnviando(false);
      }
    });
  };

  return (
    <div className="recuerdo-plan">
      <section aria-labelledby={`${idFoto}-fotos`}>
        <h2 id={`${idFoto}-fotos`}>Fotos del plan</h2>
        {fotos.length === 0 ? (
          <p className="nota">Todavía no hay fotos. Quienes se apuntaron y la organización pueden subir las suyas.</p>
        ) : (
          <ul className="galeria-plan">
            {fotos.map((f) => (
              <li key={f.id}>
                <button type="button" onClick={() => setAmpliada(f)} aria-label={`Ampliar la foto de ${f.autor}`}>
                  <img src={f.src} alt={`Foto de ${f.autor} en «${evento.titulo}»`} loading="lazy" />
                </button>
                <span>{f.autor}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby={`${idFoto}-coment`}>
        <h2 id={`${idFoto}-coment`}>Comentarios</h2>
        <div aria-live="polite">
          {cargando && <IonSpinner name="dots" aria-label="Cargando comentarios" />}
          {!cargando && mensajes.length === 0 && !error && (
            <p className="nota">¿Estuviste? Cuenta qué tal fue. Sé la primera persona en comentar.</p>
          )}
          {mensajes.map((m) => (
            <p key={m.id} className={`burbuja${m.autor_id && m.autor_id === usuario?.id ? ' burbuja--yo' : ''}`}>
              <b>{m.autor_nombre}</b>
              {m.texto}
            </p>
          ))}
        </div>
        {error && (
          <p className="error-form" role="alert">
            {error}
          </p>
        )}
        {!usuario && (
          <p className="candado">🔒 Puedes ver las fotos y leer los comentarios sin cuenta. Para escribir, crea una.</p>
        )}

        <form className="recuerdo-plan__form" onSubmit={publicar}>
          {foto && (
            <div className="recuerdo-plan__previa">
              <img src={foto} alt="Vista previa de la foto que vas a subir" />
              <IonButton fill="clear" color="danger" onClick={() => setFoto(null)} aria-label="Quitar la foto">
                <IonIcon icon={close} aria-hidden="true" />
              </IonButton>
            </div>
          )}
          <div className="chat-form">
            {conPermiso && (
              <>
                <input
                  ref={entrada}
                  id={`${idFoto}-archivo`}
                  type="file"
                  accept="image/*"
                  className="oculto-visual"
                  tabIndex={-1}
                  aria-hidden="true"
                  onChange={(e) => void elegirFoto(e)}
                />
                <IonButton
                  fill="outline"
                  onClick={() => entrada.current?.click()}
                  disabled={preparando}
                  aria-label={foto ? 'Cambiar la foto' : 'Añadir una foto'}
                >
                  {preparando ? <IonSpinner name="dots" /> : <IonIcon icon={camera} aria-hidden="true" />}
                </IonButton>
              </>
            )}
            <IonInput
              aria-label="Escribe un comentario"
              placeholder={foto ? 'Añade un texto (opcional)' : '¿Qué tal fue?'}
              fill="outline"
              value={texto}
              maxlength={1000}
              onIonInput={(e) => setTexto(e.detail.value ?? '')}
            />
            <IonButton type="submit" disabled={enviando || (!texto.trim() && !foto)}>
              {enviando ? <IonSpinner name="dots" /> : 'Publicar'}
            </IonButton>
          </div>
          {usuario && !conPermiso && (
            <p className="nota">Las fotos solo las pueden subir quienes se apuntaron al plan o lo organizaron.</p>
          )}
        </form>
      </section>

      {ampliada && (
        <div className="foto-ampliada" role="dialog" aria-modal="true" aria-label={`Foto de ${ampliada.autor}`}>
          <img src={ampliada.src} alt={`Foto de ${ampliada.autor} en «${evento.titulo}»`} />
          <p>{ampliada.autor}</p>
          <IonButton fill="solid" color="light" onClick={() => setAmpliada(null)} autoFocus>
            <IonIcon slot="start" icon={close} aria-hidden="true" />
            Cerrar
          </IonButton>
        </div>
      )}
    </div>
  );
};

export default RecuerdoPlan;
