import {
  IonButton,
  IonCheckbox,
  IonContent,
  IonHeader,
  IonInput,
  IonModal,
  IonNote,
  IonSpinner,
  IonText,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { useState } from 'react';

import {
  USAR_MOCKS,
  ErrorApi,
  actualizarPerfil,
  aE164,
  enModoRespaldo,
  pedirCodigo,
  verificarCodigo,
} from '../api/client';
import type { Categoria, Token } from '../api/types';
import { ENLACE_CANAL, NOMBRE_CANAL } from '../canal';
import SelectorGustos from '../components/SelectorGustos';

interface Props {
  abierto: boolean;
  motivo: string;
  onEntrar: (t: Token) => void;
  onCerrar: () => void;
}

// Alta en dos pasos pensada para personas mayores: nombre y móvil, y luego el código que llega por el canal de mensajería.
const ModalCuenta: React.FC<Props> = ({ abierto, motivo, onEntrar, onCerrar }) => {
  const [paso, setPaso] = useState<'datos' | 'vincular' | 'codigo'>('datos');
  const [nombre, setNombre] = useState('');
  const [movil, setMovil] = useState('');
  const [acepto, setAcepto] = useState(false);
  const [gustos, setGustos] = useState<Categoria[]>([]);
  const [codigo, setCodigo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const reiniciar = () => {
    setPaso('datos');
    setCodigo('');
    setError(null);
    setOcupado(false);
  };

  const enviarDatos = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const tel = aE164(movil);
    if (!nombre.trim()) return setError('Escribe tu nombre.');
    if (!tel) return setError('Escribe un móvil de 9 cifras, por ejemplo 600 123 456.');
    if (!acepto) return setError(`Marca la casilla para que podamos avisarte por ${NOMBRE_CANAL}.`);
    setError(null);
    await solicitarCodigo(tel);
  };

  // El bot solo puede escribir a quien ya le ha hablado: si la API responde `enviado: false`, primero hay que
  // abrir el bot y compartir el número (B8, «/start codigo»), y después volver a pedir el código.
  const solicitarCodigo = async (tel: string) => {
    setOcupado(true);
    try {
      const r = await pedirCodigo(tel);
      setPaso(r.enviado ? 'codigo' : 'vincular');
      if (!r.enviado && paso === 'vincular')
        setError(`Todavía no nos has escrito por ${NOMBRE_CANAL}. Abre el bot, pulsa «Compartir mi número» y vuelve.`);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : 'No hemos podido enviar el código. Inténtalo de nuevo.');
    } finally {
      setOcupado(false);
    }
  };

  const enviarCodigo = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const tel = aE164(movil)!;
    setOcupado(true);
    setError(null);
    try {
      const t = await verificarCodigo(tel, codigo.trim());
      let usuario = t.usuario;
      try {
        usuario = await actualizarPerfil({
          nombre: nombre.trim(),
          acepta_avisos: true,
          ...(gustos.length > 0 && { gustos }),
        });
      } catch {
        usuario = { ...usuario, nombre: nombre.trim() };
      }
      onEntrar({ ...t, usuario: { ...usuario, nombre: usuario.nombre || nombre.trim() } });
      reiniciar();
    } catch (e) {
      setError(
        e instanceof ErrorApi
          ? `El código no es correcto. Revisa ${NOMBRE_CANAL} e inténtalo otra vez.`
          : 'No hemos podido comprobar el código.',
      );
      setOcupado(false);
    }
  };

  return (
    <IonModal isOpen={abierto} onDidDismiss={() => (onCerrar(), reiniciar())} className="modal-cuenta">
      <IonHeader>
        <IonToolbar color="secondary">
          <IonTitle>
            {paso === 'datos'
              ? 'Crea tu cuenta'
              : paso === 'vincular'
                ? `Un paso en ${NOMBRE_CANAL}`
                : 'Escribe el código'}
          </IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        {paso === 'datos' ? (
          <form className="form-cuenta" onSubmit={enviarDatos} noValidate>
            <p className="motivo">{motivo}</p>
            <IonInput
              label="Tu nombre"
              labelPlacement="stacked"
              fill="outline"
              autocomplete="name"
              value={nombre}
              onIonInput={(e) => setNombre(e.detail.value ?? '')}
            />
            <IonInput
              label={`Móvil (te mandamos un código por ${NOMBRE_CANAL})`}
              labelPlacement="stacked"
              fill="outline"
              type="tel"
              inputmode="tel"
              autocomplete="tel"
              placeholder="600 123 456"
              value={movil}
              onIonInput={(e) => setMovil(e.detail.value ?? '')}
            />
            <SelectorGustos gustos={gustos} onCambio={setGustos} />
            <IonCheckbox
              checked={acepto}
              onIonChange={(e) => setAcepto(e.detail.checked)}
              labelPlacement="end"
              justify="start"
            >
              <span className="ion-text-wrap">
                Acepto que me avisen por {NOMBRE_CANAL} de los planes a los que me apunte. Puedo darme de baja cuando
                quiera.
              </span>
            </IonCheckbox>
            {error && (
              <IonText color="danger" role="alert">
                <p className="error-form">{error}</p>
              </IonText>
            )}
            <IonButton type="submit" expand="block" size="large" disabled={ocupado}>
              {ocupado ? <IonSpinner name="dots" /> : 'Continuar'}
            </IonButton>
            <IonButton expand="block" fill="outline" onClick={onCerrar}>
              Ahora no, solo quiero mirar
            </IonButton>
          </form>
        ) : paso === 'vincular' ? (
          <div className="form-cuenta">
            <p className="motivo">
              Para mandarte el código por {NOMBRE_CANAL}, antes tienes que escribir a nuestro bot una vez. Es solo esta
              vez:
            </p>
            <ol className="pasos-vincular">
              <li>Pulsa «Abrir el bot».</li>
              <li>
                En {NOMBRE_CANAL}, pulsa <strong>Compartir mi número</strong>.
              </li>
              <li>Vuelve aquí y pulsa «Ya lo he hecho».</li>
            </ol>
            {ENLACE_CANAL && (
              <IonButton
                expand="block"
                size="large"
                href={`${ENLACE_CANAL}?start=codigo`}
                target="_blank"
                rel="noopener"
              >
                Abrir el bot
              </IonButton>
            )}
            {error && (
              <IonText color="danger" role="alert">
                <p className="error-form">{error}</p>
              </IonText>
            )}
            <IonButton
              expand="block"
              fill="outline"
              disabled={ocupado}
              onClick={() => void solicitarCodigo(aE164(movil)!)}
            >
              {ocupado ? <IonSpinner name="dots" /> : 'Ya lo he hecho, pedir el código'}
            </IonButton>
            <IonButton expand="block" fill="clear" onClick={reiniciar}>
              Cambiar el móvil
            </IonButton>
          </div>
        ) : (
          <form className="form-cuenta" onSubmit={enviarCodigo} noValidate>
            <p className="motivo">
              Te hemos mandado un mensaje por {NOMBRE_CANAL} al <strong>{movil}</strong> con un código de 6 cifras.
            </p>
            {(USAR_MOCKS || enModoRespaldo()) && (
              <IonNote>Modo demo: vale cualquier código de 6 cifras, por ejemplo 123456.</IonNote>
            )}
            <IonInput
              label="Código"
              labelPlacement="stacked"
              fill="outline"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength={6}
              className="input-codigo"
              value={codigo}
              onIonInput={(e) => setCodigo(e.detail.value ?? '')}
            />
            {error && (
              <IonText color="danger" role="alert">
                <p className="error-form">{error}</p>
              </IonText>
            )}
            <IonButton type="submit" expand="block" size="large" disabled={ocupado || codigo.trim().length !== 6}>
              {ocupado ? <IonSpinner name="dots" /> : 'Crear cuenta'}
            </IonButton>
            <IonButton expand="block" fill="clear" onClick={reiniciar}>
              Cambiar el móvil
            </IonButton>
          </form>
        )}
      </IonContent>
    </IonModal>
  );
};

export default ModalCuenta;
