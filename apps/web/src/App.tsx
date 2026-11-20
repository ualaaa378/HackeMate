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
import { calendar, map, person } from 'ionicons/icons';
import { Navigate, Route } from 'react-router-dom';

import Agenda from './pages/Agenda';
import Ficha from './pages/Ficha';
import Mapa from './pages/Mapa';
import Perfil from './pages/Perfil';

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

const App: React.FC = () => (
  <IonApp>
    <IonReactRouter>
      <IonTabs>
        <IonRouterOutlet>
          <Route path="/agenda" element={<Agenda />} />
          <Route path="/mapa" element={<Mapa />} />
          <Route path="/perfil" element={<Perfil />} />
          <Route path="/evento/:id" element={<Ficha />} />
          <Route path="/" element={<Navigate to="/agenda" replace />} />
        </IonRouterOutlet>
        <IonTabBar slot="bottom">
          <IonTabButton tab="agenda" href="/agenda">
            <IonIcon aria-hidden="true" icon={calendar} />
            <IonLabel>Agenda</IonLabel>
          </IonTabButton>
          <IonTabButton tab="mapa" href="/mapa">
            <IonIcon aria-hidden="true" icon={map} />
            <IonLabel>Mapa</IonLabel>
          </IonTabButton>
          <IonTabButton tab="perfil" href="/perfil">
            <IonIcon aria-hidden="true" icon={person} />
            <IonLabel>Perfil</IonLabel>
          </IonTabButton>
        </IonTabBar>
      </IonTabs>
    </IonReactRouter>
  </IonApp>
);

export default App;
