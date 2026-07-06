# 📡 Radar de Marcas Competidoras

Sistema automatizado de monitoreo de competencia y defensa comercial.
Corre una vez al mes (día 1, 08:00) vía GitHub Actions, sin marcas
hardcodeadas: todo se define en dos tablas de Notion.

## Arquitectura

```
notion_client.py    Módulo 1 — lee/escribe Notion (marcas, precios, importadores)
penta_scraper.py    Módulo 2 — Playwright: descarga datos_{marca}.xlsx desde Penta
analyzer.py         Módulo 3 — Pandas + openpyxl: cruza, alerta, genera el reporte
whatsapp_client.py  Módulo 4 — envía el resumen mensual a WhatsApp
app.py              Módulo 5 — dashboard Streamlit
main.py             Orquestador (llamado por GitHub Actions)
.github/workflows/main_cron.yml   Módulo 6 — cron mensual
```

## Setup

### 1. Notion
Crear dos bases de datos:

**Marcas Competidoras**
| Marca_Rival | Precio_Techo_Nuestro |
|---|---|
| CAREL | 120.00 |
| DANFOSS | 95.50 |
| ... | ... |

**Registro de Importadores**
| Importador | Estado |
|---|---|
| CLIENTE ABC SA | CLIENTE |
| RIVAL IMPORT SRL | COMPETIDOR |
| ... | POR_VALIDAR / NO_COMPITE |

### 2. Secrets del repositorio (Settings → Secrets and variables → Actions)
`PENTA_USER`, `PENTA_PASS`, `NOTION_TOKEN`, `NOTION_DATABASE_ID`,
`NOTION_IMPORTADORES_DB_ID` (opcional si es una base distinta),
`WA_API_URL`, `WA_TOKEN`, `WA_CELULAR`, `STREAMLIT_DASHBOARD_URL` (opcional).

### 3. Selectores de Penta
Los selectores CSS en `penta_scraper.py` están marcados con
`# AJUSTAR SELECTOR` — reemplazar por los reales de tu cuenta de
Penta-Transaction (inspeccionar el DOM del login, buscador y botón export).

### 4. Streamlit Cloud
Apuntar la app a `app.py` en este repo. Lee `reporte_marcas_mensual.xlsx`
directo del repo, que GitHub Actions commitea cada corrida.

## Correr localmente

```bash
pip install -r requirements.txt
playwright install chromium
export PENTA_USER=... PENTA_PASS=... NOTION_TOKEN=... NOTION_DATABASE_ID=... \
       WA_API_URL=... WA_TOKEN=... WA_CELULAR=...
python main.py
streamlit run app.py
```

## Reglas de negocio (configurables sin tocar código)

- Marcas propias protegidas (nunca alertan como rivales): `COEL`, `SANHUA`, `VHM`, `K11`
  (constante `MARCAS_PROPIAS_PROTEGIDAS` en `analyzer.py`).
- Umbral de presión de precio: 20% (`UMBRAL_PRESION_PRECIO` en `analyzer.py`).
- Marcas rivales y precios techo: 100% dinámicos desde Notion.
