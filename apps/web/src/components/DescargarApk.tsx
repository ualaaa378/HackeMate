import { IonButton, IonCard, IonCardContent } from '@ionic/react';
import { useEffect, useMemo, useState } from 'react';

import { ES_APP_NATIVA } from '../servidor';
import qrcode from '../vendor/qrcode';

export const RUTA_APK = '/descargas/pueblos-unidos.apk';

/** QR en SVG (sin librerías de npm: el generador va copiado en src/vendor). */
export const CodigoQr: React.FC<{ texto: string; titulo: string }> = ({ texto, titulo }) => {
  const { n, d } = useMemo(() => {
    const qr = qrcode(0, 'M');
    qr.addData(texto);
    qr.make();
    const n = qr.getModuleCount();
    let d = '';
    for (let f = 0; f < n; f++) for (let c = 0; c < n; c++) if (qr.isDark(f, c)) d += `M${c + 4} ${f + 4}h1v1h-1z`;
    return { n, d };
  }, [texto]);
  return (
    <svg
      className="codigo-qr"
      viewBox={`0 0 ${n + 8} ${n + 8}`}
      role="img"
      aria-label={titulo}
      shapeRendering="crispEdges"
    >
      <rect width={n + 8} height={n + 8} fill="#fff" />
      <path d={d} fill="#000" />
    </svg>
  );
};

/** Mi perfil (solo en la web): enlace y QR para instalar la app Android desde el móvil. */
const DescargarApk: React.FC = () => {
  const url = `${window.location.origin}${RUTA_APK}`;
  const [hayApk, setHayApk] = useState<boolean | null>(null);

  useEffect(() => {
    let vivo = true;
    fetch(RUTA_APK, { method: 'HEAD' })
      .then((r) => {
        const tipo = r.headers.get('content-type') ?? '';
        if (vivo) setHayApk(r.ok && !tipo.includes('text/html'));
      })
      .catch(() => vivo && setHayApk(false));
    return () => {
      vivo = false;
    };
  }, []);

  if (ES_APP_NATIVA) return null;
  return (
    <IonCard>
      <IonCardContent>
        <h2 className="titulo-caja">📲 La app para Android</h2>
        {hayApk === false ? (
          <p>La app para Android estará aquí en cuanto la publiquemos. Mientras, todo funciona igual desde esta web.</p>
        ) : (
          <>
            <p>Escanea el código con la cámara del móvil o pulsa el botón para descargarla e instalarla.</p>
            <div className="descargar-apk">
              <CodigoQr texto={url} titulo="Código QR para descargar la app de Android" />
            </div>
            <IonButton expand="block" fill="outline" href={RUTA_APK} download="pueblos-unidos.apk">
              Descargar la app (APK)
            </IonButton>
            <p className="descargar-apk__nota">
              Android te pedirá permitir instalar apps de este origen la primera vez.
            </p>
          </>
        )}
      </IonCardContent>
    </IonCard>
  );
};

export default DescargarApk;
