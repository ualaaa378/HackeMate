# HackeMate — Reactiva tu pueblo

Hackathon UAL para el Desarrollo del Interior, **reto 1: "Reactiva tu pueblo: comercio y turismo inteligente"**.
Equipo de 4 estudiantes con poco tiempo: **prioridad absoluta a una demo que funcione** por encima del código perfecto.
Si hay que elegir entre una funcionalidad pulida y dos que funcionan, elegimos las dos.

## Qué construimos

Plataforma web para cuatro pueblos de Almería: **Lucainena de las Torres, Senes, Velefique y Uleila del Campo**.

1. **Negocios** publican ofertas, promociones y eventos (con ayuda de IA para redactarlos).
2. **Calendario** de actividades turísticas, culturales y deportivas.
3. **Ayuntamiento** modera las publicaciones (aprobar / rechazar). Una IA las preclasifica antes (categoría, intereses, recomendación y motivo).
4. **Visitante** descubre qué hacer por intereses, fecha y ubicación en un mapa, con búsqueda semántica y un chatbot RAG que **solo responde con nuestros datos**.
5. (Opcional) **Panel de analíticas**.

## Stack

- Python + **Streamlit** (multipágina con `pages/`)
- **SQLite** (`sqlite3` de la librería estándar, sin ORM)
- **folium** + OpenStreetMap, integrado con `streamlit-folium`
- **sentence-transformers** con `paraphrase-multilingual-MiniLM-L12-v2` para embeddings; búsqueda por similitud coseno con numpy en memoria (el volumen es pequeño, no hace falta base vectorial)
- **API de Claude** (SDK oficial `anthropic`) para el chat RAG, la redacción de publicaciones y la preclasificación
- Configuración en `.env` (cargada con `python-dotenv`)

## Estructura de carpetas

```
HackeMate/
├── app.py                  # Punto de entrada: portada y selector de rol en la sidebar
├── pages/                  # Una página Streamlit por pantalla (solo UI)
│   ├── 1_Descubrir.py      # Visitante: filtros, mapa y búsqueda semántica
│   ├── 2_Calendario.py     # Actividades por fecha
│   ├── 3_Asistente.py      # Chatbot RAG
│   ├── 4_Negocios.py       # Publicar oferta/promoción/evento (+ redactar con IA)
│   ├── 5_Ayuntamiento.py   # Cola de moderación con preclasificación IA
│   └── 6_Analiticas.py     # Panel opcional
├── core/                   # Lógica reutilizable, sin código de Streamlit salvo caché
│   ├── config.py           # Variables de .env, pueblos (coordenadas), categorías, intereses
│   ├── db.py               # Conexión SQLite, esquema y todas las consultas
│   ├── search.py           # Modelo de embeddings, indexado y búsqueda semántica
│   ├── llm.py              # Cliente Claude: chat RAG, redacción y preclasificación
│   └── maps.py             # Construcción de mapas folium
├── data/
│   ├── seed.py             # Crea la BD y la llena con datos de demo realistas
│   └── hackemate.db        # Generada; no se versiona
├── requirements.txt
├── .env.example            # Plantilla de variables (sin secretos)
└── CLAUDE.md
```

## Cómo ejecutar

```powershell
py -3.14 -m venv .venv            # 3.14: torch puede no tener wheels para 3.15
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env            # y rellenar ANTHROPIC_API_KEY
python data/seed.py               # regenera la BD de demo
streamlit run app.py
```

## Convenciones

**Código**
- Identificadores, comentarios y textos de la interfaz en **español**. Los identificadores van sin tildes ni eñes (`publicacion`, `ano`, `pueblo_id`).
- Las páginas de `pages/` solo contienen UI. La lógica va en `core/` y las páginas la importan.
- Todo el SQL vive en `core/db.py`, siempre con consultas parametrizadas (`?`), nunca con f-strings.
- Las fechas se guardan como texto ISO 8601 (`2026-12-05` o `2026-12-05T18:00`).
- Usamos `@st.cache_resource` para el modelo de embeddings y el cliente de Claude, y `@st.cache_data` para lecturas. Después de cada escritura llamamos a `st.cache_data.clear()`.
- Comentarios solo donde aporten algo que el código no dice.

**Datos y roles**
- No hay login. El rol (Visitante / Negocio / Ayuntamiento) se elige en la sidebar y se guarda en `st.session_state["rol"]`. Es una demo.
- Cada publicación tiene `estado`: `pendiente` | `aprobada` | `rechazada`. El visitante, el mapa, la búsqueda y el chat **solo ven las aprobadas**.
- Las actividades del ayuntamiento son publicaciones sin `negocio_id` y se crean ya aprobadas.
- Si una publicación no tiene coordenadas, se usan las del pueblo.

**IA (Claude)**
- SDK oficial `anthropic`, sin llamadas HTTP a mano. El modelo se lee de `CLAUDE_MODEL` en `.env` (por defecto `claude-opus-5-5`).
- Preclasificación con salidas estructuradas (`output_config.format` con JSON Schema). No usar prefill de respuesta: devuelve error en los modelos actuales.
- El chat usa streaming. Su system prompt obliga a responder solo con el contexto recuperado, a citar las publicaciones usadas y a decir que no tiene esa información cuando no esté en los datos.
- Comprobar `stop_reason` (incluido `"refusal"`) antes de leer el contenido.
- **La app tiene que funcionar sin `ANTHROPIC_API_KEY`**, aunque sea en modo reducido: el chat muestra los resultados recuperados, la preclasificación usa reglas simples y el botón de redactar se desactiva. Así una caída de red o de clave no mata la demo.

**Secretos y git**
- `.env`, `.venv/` y `data/*.db` están en `.gitignore`. Nunca se sube una clave.
- Un commit por fase terminada, con un mensaje que diga qué se puede demostrar.

## Flujo de trabajo

- Trabajamos **fase a fase**. Cada fase deja algo demostrable.
- Antes de pasar a la siguiente fase, la actual se prueba con `streamlit run app.py`: la app arranca sin errores y el flujo nuevo funciona de punta a punta en el navegador.
- Si algo bloquea más de ~20 minutos, se simplifica o se recorta. No se deja una fase a medias para empezar otra.
