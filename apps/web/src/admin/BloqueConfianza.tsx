import type { PublicadorAdmin } from '../api/types';

import { dniOculto, requisitos } from './confianza';

/** Datos del responsable (DNI oculto) y lista de requisitos para publicar sin revisión. */
const BloqueConfianza: React.FC<{ publicador: PublicadorAdmin; conRequisitos?: boolean }> = ({
  publicador: p,
  conRequisitos = true,
}) => (
  <div className="confianza">
    <h3>Responsable</h3>
    {p.responsable ? (
      <dl className="responsable">
        <dt>Nombre</dt>
        <dd>{p.responsable.nombre}</dd>
        <dt>DNI</dt>
        <dd>
          {dniOculto(p.responsable.dni)}{' '}
          {p.responsable.identidad_verificada ? (
            <span className="sello sello--ok">✔ comprobado</span>
          ) : (
            <span className="sello sello--pendiente">sin comprobar</span>
          )}
        </dd>
        <dt>Vive en</dt>
        <dd>{p.responsable.residencia}</dd>
      </dl>
    ) : (
      <p className="sin-datos">Aún no ha aportado sus datos personales (DNI y residencia).</p>
    )}
    {conRequisitos && (
      <>
        <h3>Para publicar sin revisión</h3>
        <ul className="requisitos">
          {requisitos(p).map((r) => (
            <li key={r.texto} className={r.cumple ? 'cumple' : 'falta'}>
              <span aria-hidden="true">{r.cumple ? '✔' : '✖'}</span>
              <span>
                <span className="lectores">{r.cumple ? 'Cumple: ' : 'Falta: '}</span>
                {r.texto}
              </span>
            </li>
          ))}
        </ul>
      </>
    )}
  </div>
);

export default BloqueConfianza;
