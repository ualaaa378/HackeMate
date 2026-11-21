import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { getRecomendaciones } from '../api/client';
import { CATEGORIAS, type Evento, type Usuario } from '../api/types';
import { imagenPlan } from '../eventos/imagenes';
import { fechaLarga, horaEvento } from '../utils/formato';
import { type Sugerido, sugerirParecidos } from '../utils/sugerencias';

interface Props {
  usuario: Usuario | null;
  proximos: Evento[];
  mios: Set<string>;
  recarga: number;
}

/**
 * N1: columna izquierda de la agenda en pantalla grande, debajo de «Tus planes».
 * Primero lo que recomienda la API («Para ti», con gustos e historial); si no hay nada, parecidos calculados aquí.
 */
const Sugeridos: React.FC<Props> = ({ usuario, proximos, mios, recarga }) => {
  const [deApi, setDeApi] = useState<Sugerido[]>([]);
  const usuarioId = usuario?.id;

  useEffect(() => {
    if (!usuarioId) return;
    let vivo = true;
    getRecomendaciones(usuarioId)
      .then((r) => vivo && setDeApi(r.map((x) => ({ evento: x.evento, motivo: x.motivo }))))
      .catch(() => vivo && setDeApi([]));
    return () => {
      vivo = false;
    };
  }, [usuarioId, recarga]);

  const lista = (usuarioId ? deApi : []).filter((s) => !mios.has(s.evento.id));
  const items = lista.length > 0 ? lista : sugerirParecidos(proximos, mios, usuario?.gustos ?? []);

  return (
    <section className="sugeridos" aria-labelledby="t-sugeridos">
      <h2 id="t-sugeridos" className="titulo-seccion">
        ✨ Sugeridos para ti
      </h2>
      {items.length === 0 ? (
        <p className="sugeridos__vacio">
          {usuario
            ? 'Elige tus gustos en «Mi perfil» o apúntate a un plan y te sugeriremos otros parecidos.'
            : 'Crea tu cuenta y elige tus gustos, o apúntate a un plan, y te sugeriremos otros parecidos.'}{' '}
          <Link to="/perfil">Ir a mi perfil</Link>
        </p>
      ) : (
        <ul>
          {items.map(({ evento: e, motivo }) => {
            const img = imagenPlan(e);
            return (
              <li key={e.id}>
                <Link to={`/evento/${e.id}`} className="tus-planes__plan sugeridos__plan">
                  <img src={img.miniatura} alt="" loading="lazy" decoding="async" />
                  <span>
                    <strong>{e.titulo}</strong>
                    <span>
                      {CATEGORIAS[e.categoria].emoji} {fechaLarga(e.fecha_inicio)} · {horaEvento(e)}
                    </span>
                    <span>📍 {e.municipio}</span>
                    {motivo && <span className="sugeridos__motivo">{motivo}</span>}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};

export default Sugeridos;
