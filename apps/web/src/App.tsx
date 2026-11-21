import {
  IonApp,
  IonIcon,
  IonLabel,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
  setupIonicReact,
} from '@ionic/react';
import { IonReactRouter } from '@ionic/react-router';
import { calendar, fileTrayFull, images, list, map, people, person, statsChart } from 'ionicons/icons';
import { Navigate, Route, useLocation } from 'react-router-dom';

import ProveedorAcceso from './admin/ProveedorAcceso';
import { useAcceso } from './admin/acceso';
import ProveedorSesion from './cuenta/ProveedorSesion';
import Agenda from './pages/Agenda';
import Ajustes from './pages/Ajustes';
import Creditos from './pages/Creditos';
import Ficha from './pages/Ficha';
import Mapa from './pages/Mapa';
import MisPlanes from './pages/MisPlanes';
import Perfil from './pages/Perfil';
import Proponer from './pages/Proponer';
import Recuerdos from './pages/Recuerdos';
import Bandeja from './pages/admin/Bandeja';
import EventosAdmin from './pages/admin/EventosAdmin';
import Panel from './pages/admin/Panel';
import Publicadores from './pages/admin/Publicadores';

/* Core CSS required for Ionic components to work properly */
import '@ionic/react/css/core.css';

/* Basic CSS for apps built with Ionic */
import '@ionic/react/css/normalize.css';
import '@ionic/react/css/structure.css';
import '@ionic/react/css/typography.css';

/* Optional CSS utils that can be commented out */
import '@ionic/react/css/padding.css';
import '@ionic/react/css/float-elements.css';
import '@ionic/react/css/text-alignment.css';
import '@ionic/react/css/text-transformation.css';
import '@ionic/react/css/flex-utils.css';
import '@ionic/react/css/display.css';

/* Sin modo oscuro: la plantilla es clara y así controlamos el contraste en todas las pantallas. */

/* Theme variables */
import './theme/variables.css';
import './theme/app.css';

setupIonicReact();

// Una sola app con dos zonas: la del vecino (/agenda, /mapa…) y la del ayuntamiento (/admin/…).
// La barra de abajo cambia según la zona; la de /admin depende del rol (moderador o asociación).
const Navegacion: React.FC = () => {
  const { pathname } = useLocation();
  const { rol } = useAcceso();
  const enAdmin = pathname.startsWith('/admin');
  return (
    <IonTabs>
      <IonRouterOutlet>
        <Route path="/agenda" element={<Agenda />} />
        <Route path="/mapa" element={<Mapa />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/evento/:id" element={<Ficha />} />
        <Route path="/proponer" element={<Proponer />} />
        <Route path="/mis-planes" element={<MisPlanes />} />
        <Route path="/creditos" element={<Creditos />} />
        <Route path="/ajustes" element={<Ajustes />} />
        <Route path="/recuerdos" element={<Recuerdos />} />
        <Route path="/admin/bandeja" element={<Bandeja />} />
        <Route path="/admin/eventos" element={<EventosAdmin />} />
        <Route path="/admin/publicadores" element={<Publicadores />} />
        <Route path="/admin/panel" element={<Panel />} />
        <Route
          path="/admin"
          element={<Navigate to={rol === 'publicador' ? '/admin/eventos' : '/admin/bandeja'} replace />}
        />
        <Route path="/" element={<Navigate to="/agenda" replace />} />
      </IonRouterOutlet>
      {enAdmin ? (
        <IonTabBar slot="bottom" className="barra-admin">
          {rol !== 'publicador' && (
            <IonTabButton tab="bandeja" href="/admin/bandeja">
              <IonIcon aria-hidden="true" icon={fileTrayFull} />
              <IonLabel>Bandeja</IonLabel>
            </IonTabButton>
          )}
          <IonTabButton tab="eventos" href="/admin/eventos">
            <IonIcon aria-hidden="true" icon={list} />
            <IonLabel>{rol === 'publicador' ? 'Mis planes' : 'Planes'}</IonLabel>
          </IonTabButton>
          {rol !== 'publicador' && (
            <IonTabButton tab="publicadores" href="/admin/publicadores">
              <IonIcon aria-hidden="true" icon={people} />
              <IonLabel>Asociaciones</IonLabel>
            </IonTabButton>
          )}
          {rol !== 'publicador' && (
            <IonTabButton tab="panel" href="/admin/panel">
              <IonIcon aria-hidden="true" icon={statsChart} />
              <IonLabel>Panel</IonLabel>
            </IonTabButton>
          )}
        </IonTabBar>
      ) : (
        <IonTabBar slot="bottom">
          <IonTabButton tab="agenda" href="/agenda">
            <IonIcon aria-hidden="true" icon={calendar} />
            <IonLabel>Agenda</IonLabel>
          </IonTabButton>
          <IonTabButton tab="mapa" href="/mapa">
            <IonIcon aria-hidden="true" icon={map} />
            <IonLabel>Mapa</IonLabel>
          </IonTabButton>
          <IonTabButton tab="recuerdos" href="/recuerdos" className="tab-recuerdos">
            <IonIcon aria-hidden="true" icon={images} />
            <IonLabel>Recuerdos</IonLabel>
          </IonTabButton>
          <IonTabButton tab="perfil" href="/perfil">
            <IonIcon aria-hidden="true" icon={person} />
            <IonLabel>Perfil</IonLabel>
          </IonTabButton>
        </IonTabBar>
      )}
    </IonTabs>
  );
};

const App: React.FC = () => (
  <IonApp>
    <ProveedorSesion>
      <ProveedorAcceso>
        <IonReactRouter>
          <Navegacion />
        </IonReactRouter>
      </ProveedorAcceso>
    </ProveedorSesion>
  </IonApp>
);

export default App;
