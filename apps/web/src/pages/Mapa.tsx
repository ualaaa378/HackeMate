import {
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonPage,
  IonTitle,
  IonToast,
  IonToolbar,
  useIonRouter,
  useIonViewDidEnter,
} from '@ionic/react';
import { locate } from 'ionicons/icons';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useRef, useState } from 'react';
import { Circle, MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';

import { distanciaKm, getEventos } from '../api/client';
import { CATEGORIAS, type Categoria, type Evento } from '../api/types';
import FiltrosEventos from '../components/FiltrosEventos';
import { fechaLarga, hora } from '../utils/formato';

const CENTRO_COMARCA: [number, number] = [37.15, -2.3];
const RADIO_CERCA_KM = 15;

function iconoCategoria(c: Categoria) {
  const { emoji, color } = CATEGORIAS[c];
  return L.divIcon({
    className: 'pin-evento',
    html: `<div style="background:${color}"><span>${emoji}</span></div>`,
    iconSize: [38, 38],
    iconAnchor: [19, 38],
    popupAnchor: [0, -36],
  });
}

const Mapa: React.FC = () => {
  const mapa = useRef<L.Map | null>(null);
  const router = useIonRouter();
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [municipio, setMunicipio] = useState<string>();
  const [categoria, setCategoria] = useState<Categoria>();
  const [yo, setYo] = useState<[number, number] | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    getEventos({ municipio, categoria })
      .then((p) => setEventos(p.items))
      .catch(() => setAviso('No hemos podido cargar los planes.'));
  }, [municipio, categoria]);

  // Ionic monta la pestaña oculta: sin esto Leaflet calcula mal el tamaño y el mapa sale gris.
  useIonViewDidEnter(() => {
    setTimeout(() => mapa.current?.invalidateSize(), 100);
  });

  const cercaDeMi = () => {
    if (!navigator.geolocation) {
      setAviso('Tu dispositivo no permite compartir la ubicación.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const punto: [number, number] = [pos.coords.latitude, pos.coords.longitude];
        setYo(punto);
        mapa.current?.flyTo(punto, 11);
        const cerca = eventos.filter((e) => distanciaKm(punto[0], punto[1], e.lat, e.lon) <= RADIO_CERCA_KM);
        setAviso(`${cerca.length} planes a menos de ${RADIO_CERCA_KM} km de ti`);
      },
      () => setAviso('No hemos podido obtener tu ubicación. Elige un pueblo en el filtro.'),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>🗺️ Mapa de planes</IonTitle>
          <IonButtons slot="end">
            <IonButton onClick={cercaDeMi} aria-label="Planes cerca de mí">
              <IonIcon slot="start" icon={locate} aria-hidden="true" />
              Cerca de mí
            </IonButton>
          </IonButtons>
        </IonToolbar>
      </IonHeader>
      <IonContent scrollY={false}>
        <div className="mapa-layout">
          <FiltrosEventos
            municipio={municipio}
            categoria={categoria}
            onMunicipio={setMunicipio}
            onCategoria={setCategoria}
          />
          <MapContainer ref={mapa} center={CENTRO_COMARCA} zoom={10} className="mapa">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {yo && <Circle center={yo} radius={RADIO_CERCA_KM * 1000} pathOptions={{ color: '#3880ff' }} />}
            {eventos.map((e) => (
              <Marker key={e.id} position={[e.lat, e.lon]} icon={iconoCategoria(e.categoria)}>
                <Popup>
                  <strong>{e.titulo}</strong>
                  <br />
                  {fechaLarga(e.fecha_inicio)} · {hora(e.fecha_inicio)}
                  <br />
                  📍 {e.lugar ? `${e.lugar}, ` : ''}
                  {e.municipio}
                  <br />
                  <IonButton size="small" onClick={() => router.push(`/evento/${e.id}`)}>
                    Ver plan
                  </IonButton>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
        <IonToast isOpen={!!aviso} message={aviso ?? ''} duration={3000} onDidDismiss={() => setAviso(null)} />
      </IonContent>
    </IonPage>
  );
};

export default Mapa;
