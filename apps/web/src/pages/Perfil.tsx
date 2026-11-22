import {
  IonButton,
  IonCard,
  IonCardContent,
  IonButtons,
  IonContent,
  IonHeader,
  IonInput,
  IonPage,
  IonRouterLink,
  IonText,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';

import { actualizarPerfil } from '../api/client';
import type { Categoria, Usuario } from '../api/types';
import { CONTACTO_CANAL, ENLACE_CANAL, NOMBRE_CANAL } from '../canal';
import { LogoInicio } from '../components/Marca';
import SelectorGustos from '../components/SelectorGustos';
import SelectorLetra from '../components/SelectorLetra';
import { useSesion } from '../cuenta/sesion';
import { leerEdad } from '../utils/edad';

/** Se guarda en cuanto se toca un gusto: no hay botón de guardar que olvidar. */
const TusGustos: React.FC<{ usuario: Usuario; onGuardado: (u: Usuario) => void }> = ({ usuario, onGuardado }) => {
  const [gustos, setGustos] = useState<Categoria[]>(usuario.gustos ?? []);
  const [estado, setEstado] = useState<'guardado' | 'error' | null>(null);
  const cambiar = (nuevos: Categoria[]) => {
    setGustos(nuevos);
    actualizarPerfil({ gustos: nuevos })
      .then((u) => {
        onGuardado({ ...usuario, ...u, gustos: nuevos });
        setEstado('guardado');
      })
      .catch(() => setEstado('error'));
  };
  return (
    <>
      <SelectorGustos gustos={gustos} onCambio={cambiar} />
      <p role="status" className="estado-gustos">
        {estado === 'guardado' && 'Guardado. «Para ti» te sugerirá planes con estos gustos.'}
        {estado === 'error' && <IonText color="danger">No hemos podido guardarlo. Inténtalo otra vez.</IonText>}
      </p>
    </>
  );
};

/** P4b: la edad es opcional y se guarda al salir del campo. */
const TuEdad: React.FC<{ usuario: Usuario; onGuardado: (u: Usuario) => void }> = ({ usuario, onGuardado }) => {
  const [texto, setTexto] = useState(usuario.edad != null ? String(usuario.edad) : '');
  const [estado, setEstado] = useState<{ ok: boolean; texto: string } | null>(null);
  const guardar = () => {
    const r = leerEdad(texto);
    if ('error' in r) return setEstado({ ok: false, texto: r.error });
    if (r.edad === (usuario.edad ?? null)) return;
    actualizarPerfil({ edad: r.edad })
      .then((u) => {
        onGuardado({ ...usuario, ...u, edad: r.edad });
        setEstado({ ok: true, texto: 'Edad guardada.' });
      })
      .catch(() => setEstado({ ok: false, texto: 'No hemos podido guardarla. Inténtalo otra vez.' }));
  };
  return (
    <>
      <IonInput
        className="campo-edad"
        label="Tu edad (opcional)"
        labelPlacement="stacked"
        fill="outline"
        type="text"
        inputmode="numeric"
        maxlength={3}
        placeholder="Por ejemplo: 67"
        value={texto}
        onIonInput={(e) => setTexto(e.detail.value ?? '')}
        onIonBlur={guardar}
      />
      <p role="status" className="estado-gustos">
        {estado && (estado.ok ? estado.texto : <IonText color="danger">{estado.texto}</IonText>)}
      </p>
    </>
  );
};

// Bloque 3 (H3.1): gustos, pueblo, tipo de avisos y vincular el canal de mensajería (Telegram o WhatsApp).
const Perfil: React.FC = () => {
  const { usuario, abrirCuenta, salir, actualizarUsuario } = useSesion();
  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <LogoInicio />
          </IonButtons>
          <IonTitle>👤 Mi perfil</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding contenido-lectura">
        <SelectorLetra />
        {usuario ? (
          <IonCard>
            <IonCardContent>
              <h2 className="titulo-caja">Hola, {usuario.nombre}</h2>
              <p>
                {usuario.telefono
                  ? `Te avisaremos por ${NOMBRE_CANAL} de los planes a los que te apuntes.`
                  : 'Has entrado con tu cuenta.'}
              </p>
              <TusGustos key={usuario.id} usuario={usuario} onGuardado={actualizarUsuario} />
              <TuEdad key={`edad-${usuario.id}`} usuario={usuario} onGuardado={actualizarUsuario} />
              <IonButton expand="block" fill="outline" onClick={salir}>
                Cerrar sesión
              </IonButton>
            </IonCardContent>
          </IonCard>
        ) : (
          <IonCard>
            <IonCardContent>
              <h2 className="titulo-caja">Tu cuenta</h2>
              <p>
                Para mirar la agenda y el mapa no hace falta cuenta. La necesitas para apuntarte a un plan o preguntar a
                la organización.
              </p>
              <IonButton expand="block" size="large" onClick={abrirCuenta}>
                Crear cuenta o entrar
              </IonButton>
            </IonCardContent>
          </IonCard>
        )}
        <IonCard>
          <IonCardContent>
            <h2 className="titulo-caja">Usarlo solo con {NOMBRE_CANAL}</h2>
            <p>
              Manda un audio diciendo qué te apetece hacer y te contestamos con los planes.
              {CONTACTO_CANAL && (
                <>
                  {' '}
                  Búscanos como <strong>{CONTACTO_CANAL}</strong>.
                </>
              )}
            </p>
            {ENLACE_CANAL && (
              <IonButton
                expand="block"
                fill="outline"
                color="tertiary"
                href={ENLACE_CANAL}
                target="_blank"
                rel="noopener"
              >
                Abrir {NOMBRE_CANAL}
              </IonButton>
            )}
          </IonCardContent>
        </IonCard>
        <IonCard>
          <IonCardContent>
            <h2 className="titulo-caja">¿Tienes una idea para tu pueblo?</h2>
            <p>Propón un plan: el ayuntamiento lo revisa y, si lo aprueba, sale en la agenda.</p>
            <IonButton expand="block" fill="outline" routerLink="/proponer">
              Proponer un plan
            </IonButton>
            {usuario && (
              <IonButton expand="block" fill="clear" routerLink="/mis-planes">
                📝 Mis planes propuestos
              </IonButton>
            )}
          </IonCardContent>
        </IonCard>
        <IonCard>
          <IonCardContent>
            <h2 className="titulo-caja">¿Eres del ayuntamiento?</h2>
            <p>Revisa los planes que llegan, publica los del pueblo y mira las cifras de la agenda.</p>
            <IonButton expand="block" fill="outline" routerLink="/admin">
              🏛️ Entrar en la zona del ayuntamiento
            </IonButton>
            <IonButton expand="block" fill="clear" routerLink="/alta-ayuntamiento">
              ➕ Dar de alta mi ayuntamiento
            </IonButton>
          </IonCardContent>
        </IonCard>
        <p className="enlace-creditos">
          <IonRouterLink routerLink="/creditos">Créditos de las fotos de los pueblos</IonRouterLink>
          {' · '}
          <IonRouterLink routerLink="/ajustes">Ajustes</IonRouterLink>
        </p>
      </IonContent>
    </IonPage>
  );
};

export default Perfil;
