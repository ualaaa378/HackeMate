/* Fotos de los pueblos: todas de Wikimedia Commons con licencia libre.
   Si se cambia una foto, actualizar también public/pueblos/CREDITOS.md. */

export interface FotoPueblo {
  municipio: string;
  /** Ruta sin tamaño ni extensión: se sirven `${base}-600.webp` y `${base}-1200.webp`. */
  base: string;
  alt: string;
  /** Lo que muestra la foto, en pocas palabras, para el pie. */
  que: string;
  autor: string;
  licencia: string;
  url_licencia: string;
  url_original: string;
  ancho: number;
  alto: number;
}

export const FOTOS_PUEBLOS: FotoPueblo[] = [
  {
    municipio: 'Lucainena de las Torres',
    base: 'lucainena-de-las-torres',
    alt: 'Casas blancas con tejados de teja de Lucainena de las Torres y la iglesia al fondo, entre lomas de la Sierra de Alhamilla',
    que: 'Vista del pueblo',
    autor: 'Ziegler175',
    licencia: 'CC BY-SA 4.0',
    url_licencia: 'https://creativecommons.org/licenses/by-sa/4.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Alm04LucainenaDLTorres2.jpg',
    ancho: 1200,
    alto: 709,
  },
  {
    municipio: 'Senés',
    base: 'senes',
    alt: 'Senés, un pueblo blanco recogido en la ladera de la Sierra de los Filabres, rodeado de bancales y montes verdes',
    que: 'El pueblo bajo la Sierra de los Filabres',
    autor: 'Julen Iturbe-Ormaetxe',
    licencia: 'CC BY-SA 2.0',
    url_licencia: 'https://creativecommons.org/licenses/by-sa/2.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Sen%C3%A9s_(Almer%C3%ADa).jpg',
    ancho: 1200,
    alto: 900,
  },
  {
    municipio: 'Velefique',
    base: 'velefique',
    alt: 'Velefique visto desde lo alto: un racimo de casas blancas en el valle, entre montañas y rocas de pizarra',
    que: 'Vista desde la montaña',
    autor: 'Rosario García González',
    licencia: 'CC0 (dominio público)',
    url_licencia: 'https://creativecommons.org/publicdomain/zero/1.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Velefique.jpg',
    ancho: 1200,
    alto: 900,
  },
  {
    municipio: 'Uleila del Campo',
    base: 'uleila-del-campo',
    alt: 'Calle de Uleila del Campo con casas encaladas y de piedra, y el campanario de la iglesia sobre los tejados',
    que: 'Las casas y el campanario de la iglesia',
    autor: 'Ziegler175',
    licencia: 'CC BY-SA 4.0',
    url_licencia: 'https://creativecommons.org/licenses/by-sa/4.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Alm10UleilaDelCampo2.jpg',
    ancho: 1200,
    alto: 900,
  },
  {
    municipio: 'Tahal',
    base: 'tahal',
    alt: 'Torre del castillo de Tahal, de piedra oscura y con almenas, bajo un cielo azul',
    que: 'La torre del castillo (siglo XVI)',
    autor: 'Eduardo Milla',
    licencia: 'CC BY-SA 4.0',
    url_licencia: 'https://creativecommons.org/licenses/by-sa/4.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Castillo_de_Tahal_01.jpg',
    ancho: 1200,
    alto: 900,
  },
];

export const fotoDe = (municipio?: string | null): FotoPueblo | undefined =>
  FOTOS_PUEBLOS.find((f) => f.municipio === municipio);

export const srcFoto = (f: FotoPueblo, tam: 600 | 1200): string =>
  `${import.meta.env.BASE_URL}pueblos/${f.base}-${tam}.webp`;

export const srcsetFoto = (f: FotoPueblo): string => `${srcFoto(f, 600)} 600w, ${srcFoto(f, 1200)} 1200w`;

export const creditoCorto = (f: FotoPueblo): string => `Foto: ${f.autor} · ${f.licencia}`;
