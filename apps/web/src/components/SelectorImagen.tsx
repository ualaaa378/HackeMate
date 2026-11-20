import { IonButton, IonIcon } from '@ionic/react';
import { camera, trash } from 'ionicons/icons';
import { useId, useRef, useState } from 'react';

import { comprimirImagen } from '../utils/imagen';

const LIMITE_ENTRADA = 15 * 1024 * 1024;

/** Campo opcional para añadir una foto o cartel a un plan. */
const SelectorImagen: React.FC<{ valor: string | null; onCambio: (dataUrl: string | null) => void }> = ({
  valor,
  onCambio,
}) => {
  const id = useId();
  const entrada = useRef<HTMLInputElement>(null);
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const elegir = async (ev: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = ev.target.files?.[0];
    ev.target.value = '';
    if (!archivo) return;
    if (!archivo.type.startsWith('image/')) return setError('Elige una foto (JPG, PNG o similar).');
    if (archivo.size > LIMITE_ENTRADA) return setError('La foto pesa demasiado. Prueba con otra de menos de 15 MB.');
    setError(null);
    setProcesando(true);
    try {
      onCambio(await comprimirImagen(archivo));
    } catch {
      setError('No hemos podido leer esa foto. Prueba con otra.');
    } finally {
      setProcesando(false);
    }
  };

  return (
    <div className="selector-imagen">
      <label htmlFor={id} className="selector-imagen__etiqueta">
        Foto o cartel del plan <span className="ayuda">(opcional, hace el plan más llamativo)</span>
      </label>
      <input
        ref={entrada}
        id={id}
        type="file"
        accept="image/*"
        className="oculto-visual"
        onChange={(e) => void elegir(e)}
      />
      {valor ? (
        <div className="selector-imagen__vista">
          <img src={valor} alt="Vista previa de la foto elegida para el plan" />
          <div className="selector-imagen__botones">
            <IonButton fill="outline" onClick={() => entrada.current?.click()} disabled={procesando}>
              <IonIcon slot="start" icon={camera} aria-hidden="true" />
              Cambiar
            </IonButton>
            <IonButton fill="clear" color="danger" onClick={() => onCambio(null)}>
              <IonIcon slot="start" icon={trash} aria-hidden="true" />
              Quitar
            </IonButton>
          </div>
        </div>
      ) : (
        <IonButton expand="block" fill="outline" onClick={() => entrada.current?.click()} disabled={procesando}>
          <IonIcon slot="start" icon={camera} aria-hidden="true" />
          {procesando ? 'Preparando la foto…' : 'Añadir una foto'}
        </IonButton>
      )}
      <p className="nota">Si no pones ninguna, usaremos una foto que encaje con el tipo de plan.</p>
      {error && (
        <p className="error-form" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

export default SelectorImagen;
