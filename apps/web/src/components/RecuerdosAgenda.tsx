import { IonButton, IonIcon } from '@ionic/react';
import { chatbubbleEllipses } from 'ionicons/icons';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { getEventosPasados, getMensajes } from '../api/client';
import { CATEGORIAS, type Evento } from '../api/types';
import { imagenPlan } from '../eventos/imagenes';
import { fechaLarga } from '../utils/formato';

import ComentariosRecuerdo from './ComentariosRecuerdo';

const VISIBLES = 3;
const MAXIMO = 9;

/** N1: Recuerdos dentro de la agenda en pantalla grande. En el móvil siguen en su pestaña. */
const RecuerdosAgenda: React.FC = () => {
  const [planes, setPlanes] = useState<Evento[] | null>(null);
  const [todos, setTodos] = useState(false);
  const [abierto, setAbierto] = useState<Evento | null>(null);
  const [cuentas, setCuentas] = useState<Record<string, number>>({});
  const actualizarCuenta = useCallback((id: string, n: number) => setCuentas((c) => ({ ...c, [id]: n })), []);

  useEffect(() => {
    let vivo = true;
    getEventosPasados()
      .then(async (lista) => {
        const recientes = lista.slice(0, MAXIMO);
        if (!vivo) return;
        setPlanes(recientes);
        const pares = await Promise.all(
          recientes.map((e) =>
            getMensajes(e.id)
              .then((p) => [e.id, p.items.filter((m) => m.tipo === 'comentario').length] as const)
              .catch(() => [e.id, 0] as const),
          ),
        );
        if (vivo) setCuentas(Object.fromEntries(pares));
      })
      .catch(() => vivo && setPlanes([]));
    return () => {
      vivo = false;
    };
  }, []);

  if (!planes || planes.length === 0) return null;
  const mostrados = todos ? planes : planes.slice(0, VISIBLES);
  return (
    <section className="recuerdos-agenda" aria-labelledby="t-recuerdos-agenda">
      <div className="recuerdos-agenda__cabecera">
        <h2 id="t-recuerdos-agenda" className="titulo-seccion">
          📸 Recuerdos
        </h2>
        <p>Planes que ya pasaron: mira las fotos y deja tu comentario.</p>
      </div>
      <ul className="recuerdos-agenda__lista">
        {mostrados.map((e) => {
          const img = imagenPlan(e);
          const cat = CATEGORIAS[e.categoria];
          const n = cuentas[e.id] ?? 0;
          return (
            <li key={e.id} className="recuerdo-mini">
              <img src={img.miniatura} alt="" loading="lazy" decoding="async" />
              <div className="recuerdo-mini__texto">
                <span className="recuerdo-mini__chapa" style={{ background: cat.color }}>
                  {cat.emoji} {cat.etiqueta}
                </span>
                <Link to={`/evento/${e.id}`} className="recuerdo-mini__titulo">
                  {e.titulo}
                </Link>
                <span className="recuerdo-mini__lugar">
                  📍 {e.municipio} · {fechaLarga(e.fecha_inicio)}
                </span>
                <IonButton
                  fill="outline"
                  size="small"
                  onClick={() => setAbierto(e)}
                  aria-label={
                    n > 0
                      ? `Fotos y comentarios de «${e.titulo}»: ${n} comentarios`
                      : `Fotos y comentarios de «${e.titulo}»`
                  }
                >
                  <IonIcon slot="start" icon={chatbubbleEllipses} aria-hidden="true" />
                  {n > 0 ? `Fotos y comentarios (${n})` : 'Fotos y comentarios'}
                </IonButton>
              </div>
            </li>
          );
        })}
      </ul>
      {planes.length > VISIBLES && (
        <IonButton fill="clear" onClick={() => setTodos((t) => !t)} aria-expanded={todos}>
          {todos ? 'Ver menos recuerdos' : `Ver más recuerdos (${planes.length - VISIBLES})`}
        </IonButton>
      )}
      <ComentariosRecuerdo evento={abierto} onCerrar={() => setAbierto(null)} onNuevo={actualizarCuenta} />
    </section>
  );
};

export default RecuerdosAgenda;
