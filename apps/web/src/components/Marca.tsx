import { Link, useLocation } from 'react-router-dom';

// Logo «Pueblos Unidos» y nombre de la plataforma (el mismo emblema que el icono de la APK y de la PWA).
// Es un enlace a Inicio (la agenda); si ya estás en ella, vuelve arriba.
const Marca: React.FC<{ onInicio?: () => void }> = ({ onInicio }) => {
  const { pathname } = useLocation();
  const alPulsar = () => {
    onInicio?.();
    if (pathname !== '/agenda') return;
    const contenido = document.querySelector('ion-content.contenido-agenda') as HTMLIonContentElement | null;
    void contenido?.scrollToTop(300);
  };
  return (
    <Link to="/agenda" className="marca" aria-label="Reactiva tu pueblo: ir al inicio" onClick={alPulsar}>
      <img className="marca__logo" src="/icons/logo-cabecera.png" alt="" width={44} height={44} decoding="async" />
      <span>
        <span className="marca__nombre">Reactiva tu pueblo</span>
        <span className="marca__sub">5 pueblos de Almería</span>
      </span>
    </Link>
  );
};

/** Solo el logo, para la cabecera de las demás pestañas: lleva a Inicio (o al inicio del panel en /admin). */
export const LogoInicio: React.FC<{ destino?: string }> = ({ destino = '/agenda' }) => (
  <Link
    to={destino}
    className="marca marca--mini"
    aria-label={destino === '/agenda' ? 'Ir al inicio' : 'Ir al inicio del panel'}
    title="Inicio"
  >
    <img className="marca__logo" src="/icons/logo-cabecera.png" alt="" width={36} height={36} decoding="async" />
  </Link>
);

export default Marca;
