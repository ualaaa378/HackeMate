import { IonButton, IonCard, IonCardContent, IonSpinner } from '@ionic/react';
import { useCallback, useEffect, useState } from 'react';

import IdeasIA from '../../admin/IdeasIA';
import PaginaAdmin from '../../admin/PaginaAdmin';
import { useAcceso } from '../../admin/acceso';
import { PROVEEDORES } from '../../admin/ideas';
import { getEstadisticas, getEventosAdmin, getMetricasBot, simularCaida } from '../../api/admin';
import { ErrorApi } from '../../api/client';
import { CATEGORIAS, type Categoria, type Estadisticas, type MetricasBot } from '../../api/types';

/** Fracción 0-1 (ocupación). */
const pct = (x: number | undefined) => `${Math.round((x ?? 0) * 100)} %`;
/** Porcentaje que la API ya da en escala 0-100 (pct_importadas_auto, pct_otro_pueblo). */
const pct100 = (x: number | undefined) => `${Math.round(x ?? 0)} %`;
const euros = (x: number | undefined) =>
  (x ?? 0).toLocaleString('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  });
const miles = (x: number | undefined) => (x ?? 0).toLocaleString('es-ES');

const Panel: React.FC = () => {
  const [datos, setDatos] = useState<Estadisticas | null>(null);
  const [titulos, setTitulos] = useState<Record<string, string>>({});

  const { rol } = useAcceso();

  useEffect(() => {
    if (rol !== 'moderador') return;
    void getEstadisticas().then(setDatos);
    void getEventosAdmin().then((p) => setTitulos(Object.fromEntries(p.items.map((e) => [e.id, e.titulo]))));
  }, [rol]);

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
        <Cifra valor={miles(datos.actividades)} texto="planes publicados o ya hechos" />
        <Cifra valor={pct100(datos.pct_importadas_auto)} texto="importados de Facebook y webs por la IA" />
        <Cifra valor={miles(datos.inscripciones)} texto="personas apuntadas" />
        <Cifra valor={pct(asistencia)} texto="de los apuntados fueron" />
        <Cifra valor={pct100(datos.pct_otro_pueblo)} texto="vienen de otro pueblo" />
        <Cifra valor={euros(datos.tokens?.coste_total_eur)} texto={`coste de IA en ${miles(llamadas)} llamadas`} />
      </div>

      <IdeasIA />

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

      <BotIA />

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
          <p className="nota-demo">
            {(datos.tokens?.coste_total_eur ?? 0) === 0
              ? '0 €: la demo usa solo proveedores gratuitos (Gemini, NVIDIA NIM y FreeLLM).'
              : 'Solo Claude cuesta dinero; Gemini, NVIDIA NIM y FreeLLM son gratuitos.'}
          </p>
        </IonCardContent>
      </IonCard>
    </PaginaAdmin>
  );
};

/** Estado del bot en directo y el botón para la demo de robustez: si todas las IAs caen, sigue con reglas. */
const BotIA: React.FC = () => {
  const [m, setM] = useState<MetricasBot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cambiando, setCambiando] = useState(false);

  const cargar = useCallback(() => {
    getMetricasBot()
      .then((r) => {
        setM(r);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(
          e instanceof ErrorApi ? e.message : 'El bot no responde ahora mismo. La web y la API siguen funcionando.',
        ),
      );
  }, []);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 10_000);
    return () => clearInterval(t);
  }, [cargar]);

  const caida = m?.caida_simulada ?? false;
  const alternar = async () => {
    setCambiando(true);
    try {
      const r = await simularCaida(!caida);
      setM((x) => ({ ...(x ?? {}), caida_simulada: r.activa }));
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No se ha podido avisar al bot. ¿Está arrancado?');
    } finally {
      setCambiando(false);
      cargar();
    }
  };

  const totales = Object.entries(m?.totales ?? {});
  return (
    <IonCard>
      <IonCardContent>
        <h2 className="titulo-caja">El bot en directo</h2>
        {error ? (
          <p className="nota-demo" role="alert">
            ⚠️ {error}
          </p>
        ) : !m ? (
          <IonSpinner name="dots" aria-label="Cargando" />
        ) : (
          <>
            <p aria-live="polite">
              {caida
                ? '🔴 IA caída (simulada): el bot sigue atendiendo solo con reglas.'
                : '🟢 IA funcionando: el bot usa el primer proveedor que responda.'}
              {m.eventos_en_cola ? ` · ${m.eventos_en_cola} peticiones en cola para la API.` : ''}
            </p>
            {totales.length > 0 && (
              <ul className="solapamientos">
                {totales.map(([nombre, t]) => (
                  <li key={nombre}>
                    <strong>{PROVEEDORES[nombre] ?? nombre}</strong>: {miles(t.llamadas)} llamadas,{' '}
                    {miles((t.entrada ?? 0) + (t.salida ?? 0))} tokens
                    {t.fallos ? `, ${miles(t.fallos)} fallos` : ''}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        <IonButton expand="block" color={caida ? 'success' : 'danger'} disabled={cambiando} onClick={alternar}>
          {cambiando ? <IonSpinner name="dots" /> : caida ? 'Volver a encender la IA' : 'Simular caída de la IA'}
        </IonButton>
      </IonCardContent>
    </IonCard>
  );
};

const Cifra: React.FC<{ valor: string; texto: string }> = ({ valor, texto }) => (
  <div className="cifra">
    <span className="cifra__valor">{valor}</span>
    <span className="cifra__texto">{texto}</span>
  </div>
);

export default Panel;
