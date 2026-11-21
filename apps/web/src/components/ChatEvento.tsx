import { IonButton, IonInput, IonSpinner } from '@ionic/react';
import { useCallback, useEffect, useState } from 'react';

import { enviarMensaje, getMensajes } from '../api/client';
import type { MensajeEvento } from '../api/types';
import { useSesion } from '../cuenta/sesion';

export const REFRESCO_CHAT_MS = 12_000;

// Chat de la ficha: se lee sin cuenta; para preguntar hay que tenerla.
const ChatEvento: React.FC<{ eventoId: string }> = ({ eventoId }) => {
  const { usuario, conCuenta } = useSesion();
  const [mensajes, setMensajes] = useState<MensajeEvento[]>([]);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(() => getMensajes(eventoId).then((p) => setMensajes(p.items)), [eventoId]);

  // Se vuelve a pedir cada poco mientras la ficha está abierta y la pestaña visible:
  // así se ven las preguntas de otros vecinos y las respuestas sin recargar.
  useEffect(() => {
    let vivo = true;
    const traer = (primera: boolean) =>
      getMensajes(eventoId)
        .then((p) => vivo && setMensajes(p.items))
        .catch(() => vivo && primera && setError('No hemos podido cargar las preguntas.'));
    void traer(true);
    const reloj = setInterval(() => {
      if (document.visibilityState === 'visible') void traer(false);
    }, REFRESCO_CHAT_MS);
    return () => {
      vivo = false;
      clearInterval(reloj);
    };
  }, [eventoId]);

  const enviar = (ev: React.FormEvent) => {
    ev.preventDefault();
    const t = texto.trim();
    if (!t) return;
    conCuenta('Para preguntar a la organización necesitas una cuenta. Así pueden contestarte a ti.', async (u) => {
      setEnviando(true);
      setError(null);
      try {
        await enviarMensaje(eventoId, { texto: t, tipo: 'pregunta' }, u);
        setTexto('');
        await cargar();
      } catch {
        setError('No hemos podido enviar tu pregunta. Inténtalo de nuevo.');
      } finally {
        setEnviando(false);
      }
    });
  };

  return (
    <section className="chat-evento" aria-labelledby="t-chat">
      <h2 id="t-chat">Preguntas sobre el plan</h2>
      <div aria-live="polite">
        {mensajes.length === 0 && (
          <p className="nota">Todavía no hay preguntas. ¡Sé la primera persona en preguntar!</p>
        )}
        {mensajes.map((m) => (
          <p key={m.id} className={`burbuja${m.autor_id && m.autor_id === usuario?.id ? ' burbuja--yo' : ''}`}>
            <b>{m.autor_rol === 'ia' ? 'Asistente' : m.autor_nombre}</b>
            {m.texto}
          </p>
        ))}
      </div>
      {!usuario && <p className="candado">🔒 Puedes leer las preguntas sin cuenta. Para preguntar, crea una.</p>}
      {error && <p className="error-form">{error}</p>}
      <form className="chat-form" onSubmit={enviar}>
        <IonInput
          aria-label="Escribe tu pregunta"
          placeholder="Escribe tu pregunta"
          fill="outline"
          value={texto}
          maxlength={1000}
          onIonInput={(e) => setTexto(e.detail.value ?? '')}
        />
        <IonButton type="submit" disabled={enviando || !texto.trim()}>
          {enviando ? <IonSpinner name="dots" /> : 'Enviar'}
        </IonButton>
      </form>
    </section>
  );
};

export default ChatEvento;
