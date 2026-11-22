import type { Categoria, Evento } from '../api/types';

/* Imagen de cada plan: la que suba quien lo organiza (imagen_url) o, si no hay,
   una foto ilustrativa del tipo de plan (Wikimedia Commons, licencia libre).
   Si se cambia una foto, actualizar también public/eventos/CREDITOS.md. */

export interface FotoLibre {
  alt: string;
  autor: string;
  licencia: string;
  url_licencia: string | null;
  url_original: string;
}

const BY_SA_4 = 'https://creativecommons.org/licenses/by-sa/4.0/deed.es';
const DOMINIO_PUBLICO = 'Dominio público';

export const FOTOS_PLANES = {
  procesion: {
    alt: 'Procesión de Semana Santa con nazarenos de túnica morada por una calle de Almería',
    autor: 'Eduardo Milla',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Procesi%C3%B3n_Angustias_02.jpg',
  },
  romeria: {
    alt: 'Romería de San Marcos en El Ejido: carroza adornada con flores tirada por un tractor entre la gente',
    autor: 'ANESTRELLA',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Romer%C3%ADa_San_Marcos_El_Ejido.jpg',
  },
  cruces: {
    alt: 'Azulejo pintado con una cruz de mayo adornada de flores y gente bailando alrededor',
    autor: 'CarlosVdeHabsburgo',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Cruces_de_Mayo_(Sevilla).jpg',
  },
  fuegos: {
    alt: 'Castillo de fuegos artificiales de colores en el cielo de noche',
    autor: 'German Prados',
    licencia: 'CC BY 3.0',
    url_licencia: 'https://creativecommons.org/licenses/by/3.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Castillo_De_Fuegos_Artificiales_(84575397).jpeg',
  },
  flamenco: {
    alt: 'Bailaora de flamenco con traje de lunares y mantón sobre un escenario, con público alrededor',
    autor: 'Schnobby',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Flamenco_in_Sevilla_02.jpg',
  },
  sevillanas: {
    alt: 'Parejas bailando sevillanas bajo una carpa en unas fiestas de pueblo',
    autor: 'Starkenbergg',
    licencia: 'CC0 (dominio público)',
    url_licencia: 'https://creativecommons.org/publicdomain/zero/1.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Sevillanas_Serraparera.JPG',
  },
  bachata: {
    alt: 'Pareja de baile en plena figura de bachata',
    autor: 'Terralivredance',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Professional_Bachata_Couple.jpg',
  },
  teatro: {
    alt: 'Actrices sobre un escenario iluminado en tonos cálidos durante una obra de teatro',
    autor: 'José Simón Escalona',
    licencia: 'CC0 (dominio público)',
    url_licencia: 'https://creativecommons.org/publicdomain/zero/1.0/deed.es',
    url_original:
      'https://commons.wikimedia.org/wiki/File:Representaci%C3%B3n_de_La_celestina_del_Teatro_Alberto_de_Paz_y_Mateos,_Caracas_(2007).jpg',
  },
  carrera: {
    alt: 'Corredores de montaña subiendo por un sendero de piedras entre árboles',
    autor: 'Julia Baykova',
    licencia: 'CC BY 2.0',
    url_licencia: 'https://creativecommons.org/licenses/by/2.0/deed.es',
    url_original: 'https://commons.wikimedia.org/wiki/File:Trail_Running_Lago_Orta.jpg',
  },
  senderismo: {
    alt: 'Grupo de senderistas descansando en un llano de la Sierra de los Filabres, en Tahal',
    autor: 'Ayuntamiento de Roquetas de Mar',
    licencia: DOMINIO_PUBLICO,
    url_licencia: null,
    url_original: 'https://commons.wikimedia.org/wiki/File:Ruta_senderismo_Sierra_de_los_Filabres_-_24985109473.jpg',
  },
  tapas: {
    alt: 'Tres platos de tapas de jibia en salsa con pan sobre una bandeja de bar',
    autor: 'Urci dream',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Tapas_de_jibia_en_salsa.jpg',
  },
  mantecados: {
    alt: 'Mantecados navideños en forma de estrella espolvoreados de azúcar',
    autor: 'Lobo',
    licencia: DOMINIO_PUBLICO,
    url_licencia: null,
    url_original: 'https://commons.wikimedia.org/wiki/File:Mantecados_-_Navidad_2010-2011.jpg',
  },
  cabalgata: {
    alt: 'Mucha gente en la calle esperando el paso de la cabalgata de Reyes',
    autor: 'El Pantera',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Cabalgata_de_Reyes_Magos_2022-JErez-P1600194.jpg',
  },
  halloween: {
    alt: 'Niñas y niños disfrazados de calavera y de monstruo pidiendo caramelos en un pasacalles de Halloween',
    autor: 'Silar',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:02024_1221_Trick-or-treating.jpg',
  },
  mercado: {
    alt: 'Mercadillo de productos locales y artesanía en la plaza de un pueblo',
    autor: 'Alfredo Sánchez Garzón',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Casasbajas-feriaManzana_(2018)7946.jpg',
  },
  plaza: {
    alt: 'Plaza de Lucainena de las Torres con árboles podados en forma de cubo y la sierra al fondo',
    autor: 'Inma Gasteiz',
    licencia: 'CC BY-SA 4.0',
    url_licencia: BY_SA_4,
    url_original: 'https://commons.wikimedia.org/wiki/File:Plaza_de_Lucainena_de_las_Torres,_Almer%C3%ADa.jpg',
  },
  burro: {
    alt: 'Cabeza de un burro andaluz con su cabezada, entre la gente',
    autor: 'Iván Salvía',
    licencia: DOMINIO_PUBLICO,
    url_licencia: null,
    url_original: 'https://commons.wikimedia.org/wiki/File:Alboxmonachilmotril_039.jpg',
  },
} satisfies Record<string, FotoLibre>;

export type ClaveFoto = keyof typeof FOTOS_PLANES;

/** Por orden: la primera regla que encaja decide la foto. */
const REGLAS: [RegExp, ClaveFoto][] = [
  [/burro/, 'burro'],
  [/cabalgata/, 'cabalgata'],
  [/halloween|disfraces/, 'halloween'],
  [/mantecados|navide/, 'mantecados'],
  [/tapa|postre|menu|restaurante|gastronom/, 'tapas'],
  [/carrera|trail/, 'carrera'],
  [/senderis|ruta_|excursion/, 'senderismo'],
  [/flamenco/, 'flamenco'],
  [/bachata|salsa/, 'bachata'],
  [/sevillanas|baile/, 'sevillanas'],
  [/teatro/, 'teatro'],
  [/romeria/, 'romeria'],
  [/procesion|religioso|semana_santa|besamanos/, 'procesion'],
  [/flores|cruces_de_mayo|cruz/, 'cruces'],
  [/ecomercado|mercad|artesan/, 'mercado'],
  [/pueblos_mas_bonitos/, 'plaza'],
  [/verbena|feria|fiesta_patronal|fuegos/, 'fuegos'],
];

const POR_CATEGORIA: Record<Categoria, ClaveFoto> = {
  deportiva: 'senderismo',
  cultural: 'teatro',
  fiestas: 'fuegos',
  gastronomia: 'tapas',
  ludica: 'sevillanas',
  comercio: 'mercado',
};

const sinTildes = (s: string): string => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

export function claveFotoPlan(e: Pick<Evento, 'titulo' | 'etiquetas' | 'categoria'>): ClaveFoto {
  const texto = sinTildes([...(e.etiquetas ?? []), e.titulo.replace(/\s+/g, '_')].join(' '));
  return REGLAS.find(([re]) => re.test(texto))?.[1] ?? POR_CATEGORIA[e.categoria] ?? 'fuegos';
}

export interface ImagenPlan {
  src: string;
  srcSet?: string;
  /** Versión pequeña para listas. */
  miniatura: string;
  alt: string;
  /** null cuando la imagen la ha subido quien organiza el plan. */
  credito: (FotoLibre & { clave: ClaveFoto }) | null;
}

const ruta = (clave: ClaveFoto, tam: 320 | 900): string => `${import.meta.env.BASE_URL}eventos/${clave}-${tam}.webp`;

export function imagenPlan(e: Pick<Evento, 'titulo' | 'etiquetas' | 'categoria' | 'imagen_url'>): ImagenPlan {
  if (e.imagen_url)
    return { src: e.imagen_url, miniatura: e.imagen_url, alt: `Imagen del plan «${e.titulo}»`, credito: null };
  const clave = claveFotoPlan(e);
  const foto = FOTOS_PLANES[clave];
  return {
    src: ruta(clave, 900),
    srcSet: `${ruta(clave, 320)} 320w, ${ruta(clave, 900)} 900w`,
    miniatura: ruta(clave, 320),
    alt: foto.alt,
    credito: { ...foto, clave },
  };
}

export const miniaturaPlan = (clave: ClaveFoto): string => ruta(clave, 320);
