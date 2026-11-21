import { Link } from 'react-router-dom';

import { CATEGORIAS, type Evento } from '../api/types';
import { imagenPlan } from '../eventos/imagenes';
import { fechaLarga, horaEvento } from '../utils/formato';

/** Planes a los que la persona se ha apuntado, arriba del todo en Inicio para llegar a ellos de un toque. */
const TusPlanes: React.FC<{ eventos: Evento[] }> = ({ eventos }) => {
  if (!eventos.length) return null;
  return (
    <section className="tus-planes" aria-labelledby="t-tus-planes">
      <h2 id="t-tus-planes" className="titulo-seccion">
        Tus planes
      </h2>
      <ul>
        {eventos.map((e) => {
          const img = imagenPlan(e);
          return (
            <li key={e.id}>
              <Link to={`/evento/${e.id}`} className="tus-planes__plan">
                <img src={img.miniatura} alt="" loading="lazy" decoding="async" />
                <span>
                  <strong>{e.titulo}</strong>
                  <span>
                    {CATEGORIAS[e.categoria].emoji} {fechaLarga(e.fecha_inicio)} · {horaEvento(e)}
                  </span>
                  <span>📍 {e.municipio}</span>
                  <span className="tus-planes__ok">✓ Apuntado</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default TusPlanes;
