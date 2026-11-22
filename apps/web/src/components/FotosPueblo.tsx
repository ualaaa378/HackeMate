import { Link } from 'react-router-dom';

import { FOTOS_PUEBLOS, creditoCorto, fotoDe, srcFoto, srcsetFoto } from '../pueblos/fotos';

/** Fila de tarjetas con la foto de cada pueblo. Tocar una filtra la agenda por ese pueblo. */
export const TarjetasPueblos: React.FC<{ municipio?: string; onMunicipio: (m?: string) => void }> = ({
  municipio,
  onMunicipio,
}) => (
  <section className="pueblos-fotos" aria-label="Elige tu pueblo">
    <ul>
      {FOTOS_PUEBLOS.map((f) => {
        const elegido = municipio === f.municipio;
        return (
          <li key={f.base}>
            <button
              type="button"
              className={`tarjeta-pueblo${elegido ? ' tarjeta-pueblo--elegida' : ''}`}
              aria-pressed={elegido}
              onClick={() => onMunicipio(elegido ? undefined : f.municipio)}
            >
              <img src={srcFoto(f, 600)} alt="" width={600} height={450} loading="lazy" decoding="async" />
              <span className="tarjeta-pueblo__nombre">{f.municipio}</span>
            </button>
          </li>
        );
      })}
    </ul>
  </section>
);

/** Foto grande del pueblo con su nombre y el crédito de la foto. */
export const CabeceraPueblo: React.FC<{ municipio?: string | null; compacta?: boolean }> = ({
  municipio,
  compacta,
}) => {
  const f = fotoDe(municipio);
  if (!f) return null;
  return (
    <figure className={`cabecera-pueblo${compacta ? ' cabecera-pueblo--compacta' : ''}`}>
      <img
        src={srcFoto(f, 1200)}
        srcSet={srcsetFoto(f)}
        sizes="(min-width: 900px) 900px, 100vw"
        alt={f.alt}
        width={f.ancho}
        height={f.alto}
        decoding="async"
      />
      <figcaption>
        <span className="cabecera-pueblo__nombre">{f.municipio}</span>
        <Link to="/creditos" className="cabecera-pueblo__credito">
          {creditoCorto(f)}
        </Link>
      </figcaption>
    </figure>
  );
};
