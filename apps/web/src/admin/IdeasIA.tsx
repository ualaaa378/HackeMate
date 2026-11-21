import { IonButton, IonCard, IonCardContent, IonChip, IonInput, IonSpinner, IonText } from '@ionic/react';
import { useEffect, useState } from 'react';

import { crearBorradorSugerencia, getSugerencias } from '../api/admin';
import { ErrorApi } from '../api/client';
import { CATEGORIAS, type Sugerencias, type SugerenciaPlan } from '../api/types';
import { claveDia, isoMadrid } from '../utils/formato';

import { claveIdea, guardarDescartadas, leerDescartadas, nombreProveedor, textoBasadoEn } from './ideas';

/**
 * N5b · «Ideas de la IA» (N7): la IA propone planes parecidos a los que más gente reunieron.
 * La IA propone y una persona decide: [Crear borrador] lo deja en la bandeja con la fecha que elija el moderador.
 */
const IdeasIA: React.FC = () => {
  const [datos, setDatos] = useState<Sugerencias | null>(null);
  const [error, setError] = useState(false);
  const [recarga, setRecarga] = useState(0);
  const [descartadas, setDescartadas] = useState<Set<string>>(leerDescartadas);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [fecha, setFecha] = useState('');
  const [horaTexto, setHoraTexto] = useState('11:00');
  const [creadas, setCreadas] = useState<Set<string>>(new Set());
  const [ocupado, setOcupado] = useState(false);
  const [fallo, setFallo] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    getSugerencias()
      .then((d) => {
        if (!vivo) return;
        setDatos(d);
        setError(false);
      })
      .catch(() => vivo && setError(true));
    return () => {
      vivo = false;
    };
  }, [recarga]);

  const pedirOtras = () => {
    setDatos(null);
    setError(false);
    setRecarga((n) => n + 1);
  };

  const descartar = (s: SugerenciaPlan) => {
    const nuevas = new Set(descartadas).add(claveIdea(s));
    setDescartadas(nuevas);
    guardarDescartadas(nuevas);
  };

  const recuperar = () => {
    setDescartadas(new Set());
    guardarDescartadas(new Set());
  };

  const abrir = (s: SugerenciaPlan) => {
    setAbierta(claveIdea(s));
    setFecha('');
    setFallo(null);
  };

  const crear = async (s: SugerenciaPlan) => {
    setOcupado(true);
    setFallo(null);
    try {
      await crearBorradorSugerencia({ ...s, fecha_inicio: isoMadrid(fecha, horaTexto) });
      setCreadas((c) => new Set(c).add(claveIdea(s)));
      setAbierta(null);
    } catch (e) {
      setFallo(e instanceof ErrorApi ? e.message : 'No se ha podido crear el borrador. Inténtalo otra vez.');
    } finally {
      setOcupado(false);
    }
  };

  const visibles = datos?.items.filter((s) => !descartadas.has(claveIdea(s))) ?? [];
  const planes = new Map((datos?.basado_en ?? []).map((p) => [p.evento_id, p]));
  const hoy = claveDia(new Date().toISOString());

  return (
    <IonCard className="ideas-ia">
      <IonCardContent>
        <h2 className="titulo-caja">💡 Ideas de la IA</h2>
        <p className="nota-demo">
          La IA mira los planes que más gente reunieron y propone otros parecidos. Nada se publica solo: el borrador va
          a la bandeja y lo apruebas tú.
        </p>

        {error && (
          <p role="alert">
            No hemos podido pedir ideas ahora mismo. El resto del panel sigue funcionando.{' '}
            <IonButton size="small" fill="clear" onClick={pedirOtras}>
              Reintentar
            </IonButton>
          </p>
        )}
        {!datos && !error && <IonSpinner name="dots" aria-label="Pidiendo ideas a la IA" />}

        {datos && (
          <>
            <p className="ideas-ia__proveedor">Propuestas de {nombreProveedor(datos.proveedor_ia)}</p>
            {visibles.length === 0 && (
              <p>
                No quedan ideas por revisar.
                {descartadas.size > 0 && (
                  <IonButton size="small" fill="clear" onClick={recuperar}>
                    Ver otra vez las descartadas
                  </IonButton>
                )}
              </p>
            )}
            <ul className="ideas-ia__lista">
              {visibles.map((s) => {
                const clave = claveIdea(s);
                const cat = CATEGORIAS[s.categoria];
                const base = (s.basado_en ?? []).flatMap((id) => {
                  const p = planes.get(id);
                  return p ? [textoBasadoEn(p)] : [];
                });
                return (
                  <li key={clave} className="idea">
                    <div className="idea__cabecera">
                      <IonChip outline>
                        <span aria-hidden="true">{cat?.emoji}</span> {cat?.etiqueta ?? s.categoria}
                      </IonChip>
                      <strong className="idea__titulo">{s.titulo}</strong>
                    </div>
                    <p className="idea__datos">
                      📍 {s.municipio}
                      {s.fecha_aproximada && ` · 🗓️ ${s.fecha_aproximada}`}
                    </p>
                    <p className="idea__motivo">✨ {s.motivo}</p>
                    {s.descripcion && <p className="idea__descripcion">{s.descripcion}</p>}
                    {base.length > 0 && <p className="idea__base">Basado en: {base.join(' · ')}</p>}

                    {creadas.has(clave) ? (
                      <p className="idea__hecha" role="status">
                        ✓ Borrador en la bandeja.{' '}
                        <IonButton size="small" fill="clear" routerLink="/admin/bandeja">
                          Ir a la bandeja
                        </IonButton>
                      </p>
                    ) : abierta === clave ? (
                      <form
                        className="idea__form"
                        onSubmit={(ev) => {
                          ev.preventDefault();
                          if (fecha) void crear(s);
                        }}
                      >
                        <IonInput
                          type="date"
                          label="Día"
                          labelPlacement="stacked"
                          fill="outline"
                          min={hoy}
                          value={fecha}
                          onIonInput={(e) => setFecha(e.detail.value ?? '')}
                        />
                        <IonInput
                          type="time"
                          label="Hora"
                          labelPlacement="stacked"
                          fill="outline"
                          value={horaTexto}
                          onIonInput={(e) => setHoraTexto(e.detail.value || '11:00')}
                        />
                        {fallo && (
                          <IonText color="danger" role="alert">
                            <p>{fallo}</p>
                          </IonText>
                        )}
                        <div className="idea__botones">
                          <IonButton type="submit" disabled={!fecha || ocupado}>
                            {ocupado ? <IonSpinner name="dots" /> : 'Enviar a la bandeja'}
                          </IonButton>
                          <IonButton fill="clear" onClick={() => setAbierta(null)}>
                            Cancelar
                          </IonButton>
                        </div>
                      </form>
                    ) : (
                      <div className="idea__botones">
                        <IonButton onClick={() => abrir(s)}>Crear borrador</IonButton>
                        <IonButton fill="outline" onClick={() => descartar(s)}>
                          Descartar
                        </IonButton>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
            <IonButton fill="clear" size="small" onClick={pedirOtras}>
              Pedir otras ideas
            </IonButton>
          </>
        )}
      </IonCardContent>
    </IonCard>
  );
};

export default IdeasIA;
