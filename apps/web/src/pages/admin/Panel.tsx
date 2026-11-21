import { IonCard, IonCardContent, IonSpinner } from '@ionic/react';
import { useEffect, useState } from 'react';

import PaginaAdmin from '../../admin/PaginaAdmin';
import { getEstadisticas, getEventosAdmin } from '../../api/admin';
import { CATEGORIAS, type Categoria, type Estadisticas } from '../../api/types';

const pct = (x: number | undefined) => `${Math.round((x ?? 0) * 100)} %`;
const euros = (x: number | undefined) =>
  (x ?? 0).toLocaleString('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  });
const miles = (x: number | undefined) => (x ?? 0).toLocaleString('es-ES');

const PROVEEDORES: Record<string, string> = {
  gemini: 'Gemini (principal)',
  freellm: 'FreeLLM (respaldo gratis)',
  claude: 'Claude (respaldo)',
  reglas: 'Reglas sin IA (si todo cae)',
};

const Panel: React.FC = () => {
  const [datos, setDatos] = useState<Estadisticas | null>(null);
  const [titulos, setTitulos] = useState<Record<string, string>>({});

  useEffect(() => {
    void getEstadisticas().then(setDatos);
    void getEventosAdmin().then((p) => setTitulos(Object.fromEntries(p.items.map((e) => [e.id, e.titulo]))));
  }, []);

  if (!datos)
    return (
      <PaginaAdmin titulo="📊 Panel" roles={['moderador']}>
        <div className="centrado">
          <IonSpinner aria-label="Cargando" />
        </div>
      </PaginaAdmin>
    );

  const asistencia = datos.inscripciones ? (datos.asistencias ?? 0) / datos.inscripciones : 0;
  const proveedores = Object.entries(datos.tokens?.por_proveedor ?? {});
  const llamadas = proveedores.reduce((s, [, p]) => s + (p.llamadas ?? 0), 0);

  return (
    <PaginaAdmin titulo="📊 Panel" roles={['moderador']}>
      <div className="cifras">
        <Cifra valor={miles(datos.actividades)} texto="planes publicados" />
        <Cifra valor={pct(datos.pct_importadas_auto)} texto="importados solos por la IA" />
        <Cifra valor={miles(datos.inscripciones)} texto="personas apuntadas" />
        <Cifra valor={pct(asistencia)} texto="de los apuntados fueron" />
        <Cifra valor={pct(datos.pct_otro_pueblo)} texto="vienen de otro pueblo" />
        <Cifra valor={euros(datos.tokens?.coste_total_eur)} texto={`coste de IA en ${miles(llamadas)} llamadas`} />
      </div>

      <IonCard>
        <IonCardContent>
          <h2 className="titulo-caja">Ocupación por tipo de plan</h2>
          {Object.entries(datos.ocupacion_por_categoria ?? {}).map(([cat, valor]) => {
            const c = CATEGORIAS[cat as Categoria];
            return (
              <div key={cat} className="barra">
                <span className="barra__nombre">
                  {c?.emoji} {c?.etiqueta ?? cat}
                </span>
                <span className="barra__pista" aria-hidden="true">
                  <span className="barra__relleno" style={{ width: pct(valor), background: c?.color }} />
                </span>
                <span className="barra__valor">{pct(valor)}</span>
              </div>
            );
          })}
        </IonCardContent>
      </IonCard>

      <IonCard>
        <IonCardContent>
          <h2 className="titulo-caja">Planes que se pisan</h2>
          {datos.solapamientos?.length ? (
            <ul className="solapamientos">
              {datos.solapamientos.map((s, i) => (
                <li key={i}>
                  <strong>
                    {titulos[s.evento_a ?? ''] ?? 'Un plan'} ↔ {titulos[s.evento_b ?? ''] ?? 'otro plan'}
                  </strong>
                  <br />
                  {s.motivo}
                </li>
              ))}
            </ul>
          ) : (
            <p>No hay planes que coincidan.</p>
          )}
        </IonCardContent>
      </IonCard>

      <IonCard>
        <IonCardContent>
          <h2 className="titulo-caja">Coste de la IA</h2>
          <p className="nota-demo">
            Cada mensaje al bot gasta tokens. Si un proveedor cae, se pasa al siguiente y, al final, a reglas sin IA.
          </p>
          <div className="tabla-scroll">
            <table className="tabla-tokens">
              <thead>
                <tr>
                  <th scope="col">Proveedor</th>
                  <th scope="col">Llamadas</th>
                  <th scope="col">Tokens entrada</th>
                  <th scope="col">Tokens salida</th>
                  <th scope="col">Coste</th>
                </tr>
              </thead>
              <tbody>
                {proveedores.map(([nombre, p]) => (
                  <tr key={nombre}>
                    <th scope="row">{PROVEEDORES[nombre] ?? nombre}</th>
                    <td>{miles(p.llamadas)}</td>
                    <td>{miles(p.entrada)}</td>
                    <td>{miles(p.salida)}</td>
                    <td>{euros(p.coste_eur)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td>{miles(llamadas)}</td>
                  <td colSpan={2} />
                  <td>{euros(datos.tokens?.coste_total_eur)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </IonCardContent>
      </IonCard>
    </PaginaAdmin>
  );
};

const Cifra: React.FC<{ valor: string; texto: string }> = ({ valor, texto }) => (
  <div className="cifra">
    <span className="cifra__valor">{valor}</span>
    <span className="cifra__texto">{texto}</span>
  </div>
);

export default Panel;
