// Datos de la demo para la interfaz del ayuntamiento (bandeja, publicadores y panel).
// Salen de contracts/fixtures y del guion de la demo: el caso «apuestas» de Bar La Plaza,
// un evento que entra por WhatsApp, un plan propuesto por una vecina y una asociación por aprobar.

import type { DatosResponsable, Estadisticas, Evento, PendienteBandeja, PublicadorAdmin } from '../api/types';

import publicadoresFixture from './publicadores.json';

export const COORDENADAS: Record<string, { lat: number; lon: number }> = {
  'Lucainena de las Torres': { lat: 37.0406, lon: -2.2017 },
  Senés: { lat: 37.1983, lon: -2.3447 },
  Velefique: { lat: 37.1931, lon: -2.4006 },
  'Uleila del Campo': { lat: 37.1856, lon: -2.2061 },
  Tahal: { lat: 37.2219, lon: -2.2853 },
};

const AHORA = '2026-11-20T21:30:00+01:00';

export function nuevoEventoMock(datos: Partial<Evento> & Pick<Evento, 'titulo' | 'categoria' | 'municipio'>): Evento {
  const coords = COORDENADAS[datos.municipio] ?? COORDENADAS['Senés'];
  return {
    id: crypto.randomUUID(),
    descripcion: '',
    etiquetas: [],
    lugar: null,
    lat: coords.lat,
    lon: coords.lon,
    fecha_inicio: '2026-11-28T18:00:00+01:00',
    fecha_fin: null,
    precio_eur: null,
    es_gratuito: true,
    plazas_totales: null,
    plazas_libres: null,
    inscritos: 0,
    estado: 'en_revision',
    publicador_id: null,
    publicador_nombre: null,
    imagen_url: null,
    origen: { canal: 'panel', url: null, importado_auto: false },
    moderacion: { motivo: null, score_spam: null, revisado_por: null },
    creado_en: AHORA,
    actualizado_en: AHORA,
    ...datos,
  };
}

const haceDias = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString();

// Datos del responsable y actividad reciente: aún no están en el contrato ni en los fixtures.
// DNI de ejemplo (con la letra bien calculada); no son de nadie.
const EXTRA: Record<
  string,
  { responsable: DatosResponsable | null; planes: number; rechazados: number; ultimo: number }
> = {
  'Amigos de Velefique': {
    responsable: { nombre: 'Antonio Martínez', dni: '45871236J', residencia: 'Velefique', identidad_verificada: true },
    planes: 2,
    rechazados: 0,
    ultimo: 6,
  },
  'Ayto. Lucainena de las Torres': {
    responsable: {
      nombre: 'Secretaría municipal',
      dni: '27450913E',
      residencia: 'Lucainena de las Torres',
      identidad_verificada: true,
    },
    planes: 6,
    rechazados: 0,
    ultimo: 2,
  },
  'Bar La Plaza': {
    responsable: { nombre: 'Juan Rodríguez', dni: '75302814D', residencia: 'Senés', identidad_verificada: true },
    planes: 4,
    rechazados: 0,
    ultimo: 3,
  },
  'Asociación de Mujeres de Senés': {
    responsable: { nombre: 'Encarna Sánchez', dni: '34618027Z', residencia: 'Senés', identidad_verificada: false },
    planes: 5,
    rechazados: 0,
    ultimo: 4,
  },
  'Peña Cultural Uleila': { responsable: null, planes: 3, rechazados: 0, ultimo: 10 },
  'Ayto. Tahal': {
    responsable: { nombre: 'Secretaría municipal', dni: '23016548B', residencia: 'Tahal', identidad_verificada: true },
    planes: 0,
    rechazados: 0,
    ultimo: 104,
  },
};

export const publicadoresMock: PublicadorAdmin[] = [
  ...(publicadoresFixture as PublicadorAdmin[]).map((p) => {
    const extra = EXTRA[p.nombre];
    if (!extra) return p;
    return {
      ...p,
      responsable: extra.responsable,
      actividad: {
        planes_60_dias: extra.planes,
        rechazados_60_dias: extra.rechazados,
        ultimo_plan: haceDias(extra.ultimo),
      },
    };
  }),
  {
    id: '7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a07',
    nombre: 'Club Ciclista Sierra de Tahal',
    tipo: 'asociacion',
    municipio: 'Tahal',
    descripcion: 'Salidas en bici de montaña los domingos.',
    telefono: '+34600000107',
    email: null,
    estado: 'whatsapp_verificado',
    nivel_confianza: 0,
    aprobaciones: 0,
    automatizaciones_pausadas: false,
    categorias_habituales: ['deportiva'],
    fuentes: [],
    usuario_id: null,
    creado_en: '2026-11-20T20:10:00+01:00',
    responsable: { nombre: 'Rocío Fernández', dni: '48120375M', residencia: 'Tahal', identidad_verificada: false },
    actividad: { planes_60_dias: 0, rechazados_60_dias: 0, ultimo_plan: null },
  },
];

const porNombre = (nombre: string) => publicadoresMock.find((p) => p.nombre === nombre);

const barLaPlaza = porNombre('Bar La Plaza');
const pena = porNombre('Peña Cultural Uleila');

export const pendientesMock: PendienteBandeja[] = [
  {
    tipo: 'evento',
    motivo:
      'Posible spam: anuncia apuestas con premio en metálico y repite el texto de otro mensaje de hoy. Bar La Plaza publica sin revisión, pero el antispam lo ha parado.',
    score_spam: 0.91,
    evento: nuevoEventoMock({
      titulo: 'Gran porra de apuestas: gana 500 € viendo el fútbol',
      descripcion: 'Apuesta en la barra y llévate hasta 500 €. Cuantas más apuestas, más premio. ¡Corre la voz!',
      categoria: 'ludica',
      municipio: 'Senés',
      lugar: 'Bar La Plaza',
      fecha_inicio: '2026-11-22T21:00:00+01:00',
      es_gratuito: false,
      precio_eur: 10,
      publicador_id: barLaPlaza?.id ?? null,
      publicador_nombre: 'Bar La Plaza',
      origen: { canal: 'whatsapp', url: null, importado_auto: true },
      moderacion: { motivo: null, score_spam: 0.91, revisado_por: null },
    }),
  },
  {
    tipo: 'evento',
    motivo:
      'Revisión a mano: la Peña Cultural aún no ha aportado el DNI y la residencia de su responsable. La IA ha sacado todos los datos del audio y no ve nada raro.',
    score_spam: 0.04,
    evento: nuevoEventoMock({
      titulo: 'Concierto de la banda municipal en la plaza',
      descripcion: 'La banda de música toca pasodobles y bandas sonoras. Habrá sillas para las personas mayores.',
      categoria: 'cultural',
      municipio: 'Uleila del Campo',
      lugar: 'Plaza de la Constitución',
      fecha_inicio: '2026-11-29T12:30:00+01:00',
      publicador_id: pena?.id ?? null,
      publicador_nombre: 'Peña Cultural Uleila',
      origen: { canal: 'whatsapp', url: null, importado_auto: true },
      moderacion: { motivo: null, score_spam: 0.04, revisado_por: null },
    }),
  },
  {
    tipo: 'evento',
    motivo: 'Plan propuesto por una vecina desde la app. Las propuestas vecinales siempre pasan por el ayuntamiento.',
    score_spam: 0.02,
    evento: nuevoEventoMock({
      titulo: 'Paseo de mañana hasta la ermita',
      descripcion: 'Propongo quedar para andar a ritmo tranquilo hasta la ermita y tomar un café a la vuelta.',
      categoria: 'deportiva',
      etiquetas: ['senderismo', 'propuesta_vecinal', 'publico_mayores'],
      municipio: 'Senés',
      lugar: 'Fuente de la plaza',
      fecha_inicio: '2026-11-27T10:00:00+01:00',
      publicador_nombre: 'Carmen (vecina de Senés)',
      origen: { canal: 'web', url: null, importado_auto: false },
      moderacion: { motivo: null, score_spam: 0.02, revisado_por: null },
    }),
    propuesta: {
      responsable: 'Carmen López',
      telefono: '+34600000201',
      entidad: 'particular',
      publico: 'mayores',
      necesidades: ['difusion'],
      seguro_rc: 'nose',
      observaciones: 'Si hace mal tiempo lo dejamos para la semana siguiente.',
    },
  },
  {
    tipo: 'publicador',
    motivo:
      'Ha verificado su teléfono y pide publicar planes en Tahal. Ha aportado DNI y residencia: compruébalos antes de aprobar. Empezará con revisión a mano.',
    score_spam: null,
    publicador: publicadoresMock[publicadoresMock.length - 1],
  },
];

export const estadisticasMock: Estadisticas = {
  periodo: { desde: '2026-11-01T00:00:00+01:00', hasta: '2026-11-30T23:59:59+01:00' },
  actividades: 30,
  pct_importadas_auto: 0.73,
  inscripciones: 148,
  asistencias: 121,
  ocupacion_por_categoria: {
    deportiva: 0.8,
    cultural: 0.56,
    fiestas: 0.9,
    gastronomia: 0.64,
    ludica: 0.45,
    comercio: 0.38,
  },
  pct_otro_pueblo: 0.34,
  solapamientos: [
    {
      evento_a: '9d7e4f77-d668-53af-9f88-b16e6db81f74',
      evento_b: '4de907b4-2430-5e83-b70a-528a2cf39253',
      motivo: 'Las cabalgatas de Lucainena y Uleila salen la misma tarde del 5 de enero, a 10 minutos en coche.',
    },
  ],
  tokens: {
    por_proveedor: {
      gemini: { llamadas: 212, entrada: 168_400, salida: 31_250, coste_eur: 0.04 },
      freellm: { llamadas: 37, entrada: 29_800, salida: 6_100, coste_eur: 0 },
      claude: { llamadas: 9, entrada: 7_300, salida: 1_650, coste_eur: 0.05 },
      reglas: { llamadas: 14, entrada: 0, salida: 0, coste_eur: 0 },
    },
    coste_total_eur: 0.09,
  },
};
