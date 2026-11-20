import { Link } from 'react-router-dom';

import type { Evento } from '../api/types';
import { imagenPlan } from '../eventos/imagenes';

/** Imagen grande de un plan con su crédito. Si es foto de archivo, se dice que es ilustrativa. */
const FotoPlan: React.FC<{ evento: Evento; className?: string; sizes?: string }> = ({
  evento,
  className = '',
  sizes = '(min-width: 900px) 900px, 100vw',
}) => {
  const img = imagenPlan(evento);
  return (
    <figure className={`foto-plan ${className}`}>
      <img src={img.src} srcSet={img.srcSet} sizes={img.srcSet ? sizes : undefined} alt={img.alt} decoding="async" />
      <figcaption>
        {img.credito ? (
          <Link to="/creditos">
            Foto ilustrativa · {img.credito.autor} · {img.credito.licencia}
          </Link>
        ) : (
          'Foto de la organización'
        )}
      </figcaption>
    </figure>
  );
};

export default FotoPlan;
