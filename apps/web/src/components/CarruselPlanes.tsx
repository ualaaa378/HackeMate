import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { CATEGORIAS, type Evento } from '../api/types';
import { frasePortada } from '../eventos/frases';
import { imagenPlan } from '../eventos/imagenes';
import { fechaLarga, horaEvento } from '../utils/formato';

const CADA_MS = 6000;
const prefiereQuieto = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/**
 * Próximos planes que pasan solos, con la foto de portada y una frase corta.
 * Se para al pasar el ratón o el foco y con el botón Pausar (WCAG 2.2.2); con «menos movimiento» empieza parado.
 */
const CarruselPlanes: React.FC<{ eventos: Evento[] }> = ({ eventos }) => {
  const [actual, setActual] = useState(0);
  const [pausado, setPausado] = useState(prefiereQuieto);
  const [encima, setEncima] = useState(false);
  const total = eventos.length;
  const mover = useCallback((paso: number) => setActual((i) => (i + paso + total) % total), [total]);
  const raiz = useRef<HTMLElement>(null);

  useEffect(() => {
    if (pausado || encima || total < 2) return;
    const t = window.setInterval(() => {
      if (!document.hidden) mover(1);
    }, CADA_MS);
    return () => window.clearInterval(t);
  }, [pausado, encima, total, mover]);

  if (!total) return null;
  const i = actual % total;

  return (
    <section
      ref={raiz}
      className="carrusel"
      aria-roledescription="carrusel"
      aria-label="Próximos planes"
      onMouseEnter={() => setEncima(true)}
      onMouseLeave={() => setEncima(false)}
      onFocus={() => setEncima(true)}
      onBlur={(ev) => {
        if (!raiz.current?.contains(ev.relatedTarget as Node)) setEncima(false);
      }}
    >
      <div className="carrusel__marco" aria-live={pausado || encima ? 'polite' : 'off'}>
        {eventos.map((e, n) => {
          const img = imagenPlan(e);
          const cat = CATEGORIAS[e.categoria];
          const frase = frasePortada(e);
          return (
            <Link
              key={e.id}
              to={`/evento/${e.id}`}
              className="diapo"
              hidden={n !== i}
              aria-roledescription="diapositiva"
              aria-label={`${n + 1} de ${total}: ${e.titulo}`}
            >
              <img
                className="diapo__foto"
                src={img.src}
                srcSet={img.srcSet}
                sizes={img.srcSet ? '(min-width: 900px) 900px, 100vw' : undefined}
                alt=""
                decoding="async"
                loading={n ? 'lazy' : undefined}
              />
              <span className="diapo__cuerpo">
                <span className="diapo__etiqueta">
                  {cat.emoji} {cat.etiqueta} · {e.municipio}
                </span>
                <span className="diapo__titulo">{e.titulo}</span>
                <span className="diapo__cuando">
                  {fechaLarga(e.fecha_inicio)} · {horaEvento(e)}
                </span>
                <span className="diapo__frase">
                  «{frase.texto}»<small>{frase.autor}</small>
                </span>
              </span>
            </Link>
          );
        })}
      </div>
      {total > 1 && (
        <div className="carrusel__controles">
          <button type="button" className="carrusel__btn" aria-label="Plan anterior" onClick={() => mover(-1)}>
            ‹
          </button>
          <button type="button" className="carrusel__btn" aria-label="Plan siguiente" onClick={() => mover(1)}>
            ›
          </button>
          <button
            type="button"
            className="carrusel__pausa"
            aria-pressed={pausado}
            onClick={() => setPausado((p) => !p)}
          >
            {pausado ? '▶ Seguir' : '⏸ Pausar'}
          </button>
          <div className="carrusel__puntos">
            {eventos.map((e, n) => (
              <button
                key={e.id}
                type="button"
                aria-label={`Ir al plan ${n + 1}`}
                aria-current={n === i}
                onClick={() => setActual(n)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

export default CarruselPlanes;
