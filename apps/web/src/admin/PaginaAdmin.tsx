import {
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonContent,
  IonHeader,
  IonInput,
  IonItem,
  IonPage,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';
import { Navigate } from 'react-router-dom';

import { PERFILES_AYUNTAMIENTO } from '../api/admin';
import { NOMBRE_CANAL } from '../canal';
import { LogoInicio } from '../components/Marca';
import SelectorLetra from '../components/SelectorLetra';
import { useSesion } from '../cuenta/sesion';

import { type ResultadoAcceso, type RolAdmin, useAcceso } from './acceso';

/** Marco de todas las pantallas de /admin. Sin rol de moderador o publicador enseña la puerta de entrada. */
const PaginaAdmin: React.FC<{
  titulo: string;
  roles?: RolAdmin[];
  acciones?: React.ReactNode;
  children: React.ReactNode;
}> = ({ titulo, roles = ['moderador', 'publicador'], acciones, children }) => {
  const acceso = useAcceso();
  const permitido = acceso.rol != null && roles.includes(acceso.rol);
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <LogoInicio destino="/admin" />
          </IonButtons>
          <IonTitle>{titulo}</IonTitle>
          <IonButtons slot="end">{permitido && acciones}</IonButtons>
        </IonToolbar>
        {acceso.rol && (
          <div className="franja-admin" role="note">
            <span>
              {acceso.rol === 'moderador' ? '🏛️' : '🤝'} {acceso.nombre}
              {acceso.demo && ' · modo demo'}
            </span>
            <SelectorLetra compacto />
            <IonButton size="small" fill="clear" routerLink="/agenda" onClick={acceso.salir}>
              Salir
            </IonButton>
          </div>
        )}
      </IonHeader>
      <IonContent className="ion-padding contenido-admin">
        {!acceso.rol && <SelectorLetra />}
        {permitido ? children : <Puerta rolActual={acceso.rol} />}
      </IonContent>
    </IonPage>
  );
};

const MENSAJES: Record<Exclude<ResultadoAcceso, 'ok'>, string> = {
  credenciales: 'Usuario o contraseña incorrectos.',
  bloqueado: 'Demasiados intentos fallidos. Espera unos minutos y vuelve a probar.',
  sin_api: 'Ahora no se puede comprobar el acceso. Inténtalo de nuevo en un momento.',
};

/** Moderación del ayuntamiento: usuario y contraseña (POST /auth/admin). */
const AccesoModeracion: React.FC = () => {
  const { entrarAdmin } = useAcceso();
  const [usuario, setUsuario] = useState('');
  const [contrasena, setContrasena] = useState('');
  const [entrando, setEntrando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enviar = (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!usuario.trim() || !contrasena) {
      setError('Escribe el usuario y la contraseña.');
      return;
    }
    setEntrando(true);
    setError(null);
    void entrarAdmin(usuario.trim(), contrasena)
      .then((r) => {
        if (r !== 'ok') {
          setError(MENSAJES[r]);
          setContrasena('');
        }
      })
      .finally(() => setEntrando(false));
  };
  return (
    <form className="acceso-moderacion" onSubmit={enviar} noValidate>
      <h3>🏛️ Moderación del ayuntamiento</h3>
      <IonItem>
        <IonInput
          label="Usuario"
          labelPlacement="stacked"
          autocomplete="username"
          autocapitalize="off"
          value={usuario}
          onIonInput={(ev) => setUsuario(ev.detail.value ?? '')}
        />
      </IonItem>
      <IonItem>
        <IonInput
          label="Contraseña"
          labelPlacement="stacked"
          type="password"
          autocomplete="current-password"
          value={contrasena}
          onIonInput={(ev) => setContrasena(ev.detail.value ?? '')}
        />
      </IonItem>
      {error && (
        <p className="error-acceso" role="alert">
          {error}
        </p>
      )}
      <IonButton expand="block" size="large" type="submit" disabled={entrando}>
        {entrando ? 'Comprobando…' : 'Entrar'}
      </IonButton>
    </form>
  );
};

const Puerta: React.FC<{ rolActual: RolAdmin | null }> = ({ rolActual }) => {
  const { entrarDemo } = useAcceso();
  const { abrirCuenta } = useSesion();
  const [entrando, setEntrando] = useState(false);
  const entrar = (r: RolAdmin, usuarioId?: string) => {
    setEntrando(true);
    void entrarDemo(r, usuarioId).finally(() => setEntrando(false));
  };
  return (
    <IonCard className="puerta-admin">
      <IonCardContent>
        {rolActual ? (
          // El ayuntamiento solo tiene «Mis planes»: si cae en otra sección (p. ej. /admin/bandeja), se la lleva allí.
          <Navigate to="/admin/eventos" replace />
        ) : (
          <>
            <h2 className="titulo-caja">Zona del ayuntamiento</h2>
            <p>
              Aquí se revisan los planes que llegan por {NOMBRE_CANAL} o la web, se aprueban las asociaciones que piden
              publicar y se ven las cifras de la agenda.
            </p>
            <AccesoModeracion />
            <p className="nota-demo">Asociaciones: entra con tu móvil.</p>
            <IonButton expand="block" fill="outline" onClick={abrirCuenta}>
              Entrar con mi móvil
            </IonButton>
            <p className="nota-demo">Ayuntamientos: cada uno ya tiene su perfil.</p>
            {PERFILES_AYUNTAMIENTO.map((p) => (
              <IonButton
                key={p.usuarioId}
                expand="block"
                fill="outline"
                disabled={entrando}
                onClick={() => entrar('publicador', p.usuarioId)}
              >
                🏛️ {p.nombre}
              </IonButton>
            ))}
            <IonButton expand="block" fill="clear" routerLink="/agenda">
              Volver a la agenda
            </IonButton>
          </>
        )}
      </IonCardContent>
    </IonCard>
  );
};

export default PaginaAdmin;
