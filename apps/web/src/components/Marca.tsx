// Logo «Pueblos Unidos» y nombre de la plataforma (el mismo emblema que el icono de la APK y de la PWA).
const Marca: React.FC = () => (
  <div className="marca">
    <img className="marca__logo" src="/icons/logo-cabecera.png" alt="" width={44} height={44} decoding="async" />
    <span>
      <span className="marca__nombre">Reactiva tu pueblo</span>
      <span className="marca__sub">5 pueblos de Almería</span>
    </span>
  </div>
);

export default Marca;
