import {
  IonButton,
  IonContent,
  IonHeader,
  IonIcon,
  IonModal,
  IonPage,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { chatbubbleEllipses, close, informationCircle } from 'ionicons/icons';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { getEventosPasados, getMensajes } from '../api/client';
import { CATEGORIAS, type Evento } from '../api/types';
import RecuerdoPlan from '../components/RecuerdoPlan';
import { imagenPlan } from '../eventos/imagenes';
import { fechaLarga } from '../utils/formato';

/* Tablón de planes que ya han pasado: una tarjeta a pantalla completa por plan, se pasa con el dedo
   hacia arriba (como los vídeos verticales) y cada una tiene sus comentarios. */

const Recuerdos: React.FC = () => {
  const [planes, setPlanes] = useState<Evento[] | null>(null);
  const [error, setError] = useState(false);
  const [abierto, setAbierto] = useState<Evento | null>(null);
  const [cuentas, setCuentas] = useState<Record<string, number>>({});
  const actualizarCuenta = useCallback((id: string, n: number) => setCuentas((c) => ({ ...c, [id]: n })), []);

  useEffect(() => {
    let vivo = true;
    getEventosPasados()
      .then(async (lista) => {
        if (!vivo) return;
        setPlanes(lista);
        const pares = await Promise.all(
          lista.map((e) =>
            getMensajes(e.id)
              .then((p) => [e.id, p.items.filter((m) => m.tipo === 'comentario').length] as const)
              .catch(() => [e.id, 0] as const),
          ),
        );
        if (vivo) setCuentas(Object.fromEntries(pares));
      })
      .catch(() => vivo && setError(true));
    return () => {
      vivo = false;
    };
  }, []);

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>📸 Recuerdos</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent scrollY={false} className="contenido-recuerdos">
        {!planes && !error && (
          <div className="centrado">
            <IonSpinner aria-label="Cargando" />
          </div>
        )}
        {error && (
          <p className="ion-padding">No hemos podido cargar los recuerdos. Inténtalo de nuevo en un momento.</p>
        )}
        {planes && planes.length === 0 && (
          <p className="ion-padding">Todavía no hay planes pasados. Cuando acabe uno, aparecerá aquí.</p>
        )}
        {planes && planes.length > 0 && (
          <div className="feed-recuerdos" aria-label="Planes que ya han pasado. Desliza hacia arriba para ver más.">
            {planes.map((e, i) => (
              <TarjetaRecuerdo
                key={e.id}
                evento={e}
                comentarios={cuentas[e.id] ?? 0}
                cargarPronto={i < 2}
                onComentarios={() => setAbierto(e)}
              />
            ))}
          </div>
        )}
        <Comentarios evento={abierto} onCerrar={() => setAbierto(null)} onNuevo={actualizarCuenta} />
      </IonContent>
    </IonPage>
  );
};

const TarjetaRecuerdo: React.FC<{
  evento: Evento;
  comentarios: number;
  cargarPronto: boolean;
  onComentarios: () => void;
}> = ({ evento: e, comentarios, cargarPronto, onComentarios }) => {
  const img = imagenPlan(e);
  const cat = CATEGORIAS[e.categoria];
  return (
    <article className="recuerdo" aria-labelledby={`r-${e.id}`}>
      <img
        className="recuerdo__foto"
        src={img.src}
        srcSet={img.srcSet}
        sizes="100vw"
        alt={img.alt}
        loading={cargarPronto ? 'eager' : 'lazy'}
        decoding="async"
      />
      <div className="recuerdo__texto">
        <span className="recuerdo__chapa" style={{ background: cat.color }}>
          {cat.emoji} {cat.etiqueta}
        </span>
        <h2 id={`r-${e.id}`}>{e.titulo}</h2>
        <p>
          📍 {e.municipio} · {fechaLarga(e.fecha_inicio)}
        </p>
        {e.descripcion && <p className="recuerdo__desc">{e.descripcion}</p>}
        {img.credito && (
          <Link to="/creditos" className="recuerdo__credito">
            Foto ilustrativa · {img.credito.autor} · {img.credito.licencia}
          </Link>
        )}
      </div>
      <div className="recuerdo__acciones">
        <button
          type="button"
          onClick={onComentarios}
          aria-label={`Fotos y comentarios de «${e.titulo}»: ${comentarios} comentarios`}
        >
          <IonIcon icon={chatbubbleEllipses} aria-hidden="true" />
          <span>{comentarios}</span>
        </button>
        <Link to={`/evento/${e.id}`} aria-label={`Ver la ficha de «${e.titulo}»`}>
          <IonIcon icon={informationCircle} aria-hidden="true" />
          <span>Ficha</span>
        </Link>
      </div>
    </article>
  );
};

const Comentarios: React.FC<{
  evento: Evento | null;
  onCerrar: () => void;
  onNuevo: (eventoId: string, total: number) => void;
}> = ({ evento, onCerrar, onNuevo }) => {
  const id = evento?.id;
  const alCambiar = useCallback((n: number) => id && onNuevo(id, n), [id, onNuevo]);
  return (
    <IonModal
      isOpen={!!evento}
      onDidDismiss={onCerrar}
      initialBreakpoint={0.75}
      breakpoints={[0, 0.5, 0.75, 1]}
      className="hoja-comentarios"
    >
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>Fotos y comentarios</IonTitle>
          <IonButton slot="end" fill="clear" color="light" onClick={onCerrar} aria-label="Cerrar">
            <IonIcon icon={close} aria-hidden="true" />
          </IonButton>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        {evento && (
          <>
            <p className="hoja-comentarios__plan">{evento.titulo}</p>
            <RecuerdoPlan evento={evento} onTotal={alCambiar} />
          </>
        )}
      </IonContent>
    </IonModal>
  );
};

export default Recuerdos;
