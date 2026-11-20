# Datos reales de los pueblos: fuentes y criterios

Recopilado el 20/11/2026. Todo dato de `eventos.json` y `lugares.json` sale de una fuente pública y lleva su URL (`origen.url` en eventos, `fuentes` en lugares). No se ha inventado nada: cuando falta un dato (hora, precio, plazas), el campo va a `null` o lleva la etiqueta correspondiente.

## Ficheros

| Fichero | Qué contiene |
|---|---|
| `eventos.json` | 22 eventos reales (cumple `schemas/evento.json`). Los usa la app como mock. |
| `lugares.json` | 35 lugares permanentes: rutas, sitios que ver, comercios, alojamientos y servicios (cumple `schemas/lugar.json`, nuevo). |
| `eventos_demo.json` | 10 eventos inventados para la demo. No son reales. Los 8 primeros están publicados; los 2 últimos están `en_revision` para que la bandeja del moderador no salga vacía (un taller de la Asociación Juvenil de Tahal, publicador nuevo de nivel 0, y un post de apuestas de Bar La Plaza parado por el antispam). |

## Cómo están clasificados

Se usan las 6 categorías del contrato, sin añadir ninguna:

| Categoría | Qué entra | Eventos |
|---|---|---|
| `fiestas` | Patronales, romerías, Reyes, Semana Santa, cultos religiosos | 12 |
| `cultural` | Teatro, talleres y espectáculos de baile, actos institucionales | 5 |
| `gastronomia` | Rutas de la tapa, menús de restaurantes | 2 |
| `deportiva` | Carreras y pruebas deportivas | 1 |
| `ludica` | Halloween, concursos de disfraces | 1 |
| `comercio` | Productos a la venta (lata navideña de Monte-Sión) | 1 |

Los lugares van por `tipo`: `ruta` (8), `sitio_interes` (19), `comercio` (2), `alojamiento` (2), `servicio` (4).

## Estado de cada evento

- **`publicado`, fecha confirmada** (4): teatro en Uleila (21/11), Ruta de la Tapa y el Postre en Uleila (28/11), lata navideña de Monte-Sión y menú de El Museo en Lucainena.
- **`publicado`, etiqueta `fecha_estimada`** (8): fiestas anuales de 2027 cuya regla de fecha publica la fuente (por ejemplo, «último domingo de abril»). La app las marca como «Fecha estimada».
- **`finalizado`** (10): eventos de 2026 que ya pasaron. No salen en la agenda; sirven de histórico y para analíticas.

Etiquetas especiales: `sin_hora` (la fuente no da hora; la app muestra «Hora por confirmar») y `fecha_estimada`.

## Contador de apuntados

Nuevo campo `inscritos` (entero, opcional, por defecto 0) en `schemas/evento.json`. Es un cambio que solo añade. En los eventos reales empieza en 0 porque nadie se ha apuntado aún por la app; en `eventos_demo.json` se calcula como `plazas_totales - plazas_libres`. La API debe devolver el número de inscripciones confirmadas.

## Qué dio cada fuente

**Facebook (leído con sesión el 20/11/2026).** Solo 5 de las 20 páginas tienen publicaciones de 2026:
- Ayuntamiento de Uleila del Campo: la más útil (fiestas, teatro, ruta de la tapa, Halloween, flamenco).
- Ayuntamiento de Lucainena de las Torres: cultos de Monte-Sión, Día de los Pueblos más Bonitos, menú de El Museo, escuelas deportivas.
- Monte-Sión (parroquia): procesión y lata navideña.
- Ayuntamiento de Senés: talleres de sevillanas y bachata de agosto.
- CD Lucainena: partidos de fútbol sala fuera de casa (no incluidos: no son en el pueblo).

Sin actividad reciente: Lucainena. Un paraíso (comparte), Polopos (2020), Punto Vuela (solo avisos), Tercera Edad El Peñón (2021), Senés comunidad (2016), Casa Rural El Laurel (2024), Ayuntamiento de Velefique (2023), Velefique International Freeride (2022), 3.ª y 4.ª Ruta Velefique (2013-2014), Lavadero (2020), Guadalinfo Velefique, Uleila foto a foto, Protección Civil Uleila (2023) y Gimnasio Uleila (vacía). De ellas se han sacado solo datos permanentes (direcciones, teléfonos, descripción).

**Webs.** tuscasasrurales, andalucia.com, andalucia.org, myalmeria, Komoot (Senés y Velefique), Bikemap, PDF de la Diputación (material didáctico sobre Senés), visitingalmeria, euroweeklynews, festivalesdeespana, gotrail e hispanopedia. El blog «Senés y sus siete maravillas» de TierrasSinFronteras no aparece en buscadores.

## Huecos y discrepancias

- **Velefique** no tiene ningún evento con fecha en las fuentes: solo rutas y sitios.
- **Moros y Cristianos de Senés:** las fuentes no coinciden («inicios de agosto», «primera quincena de agosto», «último fin de semana de agosto»), así que no se ha estimado la fecha de 2027.
- **Romería a Monteagud (Uleila):** en abril según andalucia.com y en septiembre según festivalesdeespana. Se ha usado abril («Romería Chica»).
- **Coordenadas:** salvo el Centro de Interpretación de Senés, todo usa las coordenadas del pueblo (`coordenadas_exactas: false` en lugares).

## Datos generales útiles para el chat

- Senés: unos 288 habitantes (2023), 995 m de altitud, a 50 km de Almería. Gastronomía: migas, sopa de ajo, olla de trigo, choto al ajillo, gazpacho dulce, roscos, bollos de nata y empanadillas de calabaza (andalucia.com).
- Lucainena de las Torres: uno de los Pueblos más Bonitos de España; pasado minero (hierro desde 1896, ferrocarril hasta Agua Amarga). Patrona: Virgen de Monte-Sión, «Reina de las Flores».
- Uleila del Campo: patrón Santo Cristo de las Penas (septiembre).
