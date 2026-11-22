import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonCard,
  IonCardContent,
  IonContent,
  IonHeader,
  IonInput,
  IonPage,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonText,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';

import { ErrorApi, MUNICIPIOS, altaAyuntamiento } from '../api/client';
import type { PublicadorCrear } from '../api/types';
import { useSesion } from '../cuenta/sesion';
import { dniValido } from '../utils/dni';
import { leerEdad } from '../utils/edad';

/**
 * Alta de un ayuntamiento desde la web o el APK (solo ayuntamientos, decisión del 22/11). Queda «solicitado» hasta
 * que la moderación lo aprueba en Panel → Entidades. El teléfono es el de la cuenta: la API no acepta otro.
 */
const AltaAyuntamiento: React.FC = () => {
  const { usuario, conCuenta } = useSesion();
  const [f, setF] = useState({
    municipio: MUNICIPIOS[0],
    nombre: `Ayuntamiento de ${MUNICIPIOS[0]}`,
    email: '',
    responsable: '',
    dni: '',
    residencia: '',
    edad: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [hecho, setHecho] = useState<{ demo: boolean } | null>(null);
  const cambiar = (campo: keyof typeof f) => (valor: string) => setF((x) => ({ ...x, [campo]: valor }));

  const validar = (): string | null => {
    if (f.nombre.trim().length < 2) return 'Escribe el nombre del ayuntamiento.';
    if (f.responsable.trim().split(/\s+/).length < 2)
      return 'Escribe el nombre y al menos un apellido del responsable.';
    if (!dniValido(f.dni)) return 'Ese DNI o NIE no es válido: revisa los números y la letra.';
    if (f.residencia.trim().length < 2) return 'Escribe dónde vive el responsable.';
    if (f.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) return 'Ese correo no parece válido.';
    const edad = leerEdad(f.edad);
    if ('error' in edad) return edad.error;
    return null;
  };

  const enviar = () => {
    const fallo = validar();
    setError(fallo);
    if (fallo) return;
    conCuenta('Para dar de alta tu ayuntamiento necesitas una cuenta con tu teléfono.', async (u) => {
      if (!u.telefono) {
        setError('Tu cuenta no tiene teléfono. Entra con tu número para poder dar de alta el ayuntamiento.');
        return;
      }
      const edad = leerEdad(f.edad);
      const datos: PublicadorCrear = {
        nombre: f.nombre.trim(),
        tipo: 'ayuntamiento',
        municipio: f.municipio,
        telefono: u.telefono,
        email: f.email.trim() || null,
        responsable: {
          nombre: f.responsable.trim(),
          dni: f.dni.trim(),
          residencia: f.residencia.trim(),
          edad: 'edad' in edad ? edad.edad : null,
        },
      };
      setEnviando(true);
      try {
        setHecho(await altaAyuntamiento(datos));
      } catch (e) {
        setError(
          e instanceof ErrorApi
            ? e.code === 'publicador_ya_existe'
              ? 'Tu teléfono ya tiene una entidad dada de alta. Entra en la zona del ayuntamiento.'
              : e.message
            : 'No hemos podido enviarlo. Inténtalo en un momento.',
        );
      } finally {
        setEnviando(false);
      }
    });
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar color="secondary">
          <IonButtons slot="start">
            <IonBackButton defaultHref="/perfil" text="Volver" />
          </IonButtons>
          <IonTitle>🏛️ Dar de alta un ayuntamiento</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding contenido-lectura">
        {hecho ? (
          <IonCard>
            <IonCardContent>
              <h2 className="titulo-caja">✅ Solicitud enviada</h2>
              <p>
                <strong>{f.nombre}</strong> queda pendiente de que la moderación lo revise. Te avisaremos en cuanto esté
                aprobado; desde entonces podrás publicar los planes del pueblo.
              </p>
              {hecho.demo && (
                <p>
                  <IonText color="medium">Modo demo: no se ha enviado nada a la plataforma.</IonText>
                </p>
              )}
              <IonButton expand="block" routerLink="/perfil">
                Volver a mi perfil
              </IonButton>
            </IonCardContent>
          </IonCard>
        ) : (
          <IonCard>
            <IonCardContent>
              <p>
                Solo los ayuntamientos publican en nombre del pueblo. Pedimos los datos de la persona responsable para
                comprobar quién está detrás: solo los ve la moderación.
                {usuario?.telefono && (
                  <>
                    {' '}
                    El teléfono de contacto será el de tu cuenta (<strong>{usuario.telefono}</strong>).
                  </>
                )}
              </p>
              <IonSelect
                label="Pueblo"
                labelPlacement="stacked"
                fill="outline"
                value={f.municipio}
                onIonChange={(e) => {
                  const m = String(e.detail.value);
                  setF((x) => ({
                    ...x,
                    municipio: m,
                    nombre: x.nombre.startsWith('Ayuntamiento de ') ? `Ayuntamiento de ${m}` : x.nombre,
                  }));
                }}
              >
                {MUNICIPIOS.map((m) => (
                  <IonSelectOption key={m} value={m}>
                    {m}
                  </IonSelectOption>
                ))}
              </IonSelect>
              <IonInput
                label="Nombre del ayuntamiento"
                labelPlacement="stacked"
                fill="outline"
                value={f.nombre}
                maxlength={160}
                onIonInput={(e) => cambiar('nombre')(e.detail.value ?? '')}
              />
              <IonInput
                label="Correo del ayuntamiento (opcional)"
                labelPlacement="stacked"
                fill="outline"
                type="email"
                value={f.email}
                onIonInput={(e) => cambiar('email')(e.detail.value ?? '')}
              />
              <h3 className="titulo-caja">Persona responsable</h3>
              <IonInput
                label="Nombre y apellidos"
                labelPlacement="stacked"
                fill="outline"
                autocomplete="name"
                value={f.responsable}
                maxlength={120}
                onIonInput={(e) => cambiar('responsable')(e.detail.value ?? '')}
              />
              <IonInput
                label="DNI o NIE"
                labelPlacement="stacked"
                fill="outline"
                placeholder="12345678Z"
                value={f.dni}
                maxlength={20}
                onIonInput={(e) => cambiar('dni')(e.detail.value ?? '')}
              />
              <IonInput
                label="Pueblo o dirección donde vive"
                labelPlacement="stacked"
                fill="outline"
                value={f.residencia}
                maxlength={200}
                onIonInput={(e) => cambiar('residencia')(e.detail.value ?? '')}
              />
              <IonInput
                label="Edad (opcional)"
                labelPlacement="stacked"
                fill="outline"
                inputmode="numeric"
                maxlength={3}
                value={f.edad}
                onIonInput={(e) => cambiar('edad')(e.detail.value ?? '')}
              />
              {error && (
                <p role="alert">
                  <IonText color="danger">{error}</IonText>
                </p>
              )}
              <IonButton expand="block" size="large" onClick={enviar} disabled={enviando}>
                {enviando ? <IonSpinner name="dots" /> : 'Enviar solicitud'}
              </IonButton>
            </IonCardContent>
          </IonCard>
        )}
      </IonContent>
    </IonPage>
  );
};

export default AltaAyuntamiento;
