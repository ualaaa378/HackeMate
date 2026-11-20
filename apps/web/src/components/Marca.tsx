// Logo y nombre de la plataforma, al estilo de la cabecera de la plantilla.
const Marca: React.FC = () => (
  <div className="marca">
    <span className="marca__logo" aria-hidden="true">
      HM
    </span>
    <span>
      <span className="marca__nombre">Reactiva tu pueblo</span>
      <span className="marca__sub">Agenda de 5 pueblos de Almería</span>
    </span>
  </div>
);

export default Marca;
