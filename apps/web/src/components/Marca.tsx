import { Link } from 'react-router-dom';

// Logo «Pueblos Unidos» y nombre de la plataforma (el mismo emblema que el icono de la APK y de la PWA).
// Como en cualquier web, pulsar la marca lleva al inicio (la agenda).
const Marca: React.FC<{ onInicio?: () => void }> = ({ onInicio }) => (
  <Link to="/agenda" className="marca" aria-label="Reactiva tu pueblo: ir al inicio" onClick={onInicio}>
    <img className="marca__logo" src="/icons/logo-cabecera.png" alt="" width={44} height={44} decoding="async" />
    <span>
      <span className="marca__nombre">Reactiva tu pueblo</span>
      <span className="marca__sub">5 pueblos de Almería</span>
    </span>
  </Link>
);

export default Marca;
