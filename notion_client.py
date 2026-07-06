"""
notion_client.py
=================
Módulo 1 — Sincronización Dinámica con Notion.

Responsable de:
  1. Leer la tabla "Marcas Competidoras" (Marca_Rival, Precio_Techo_Nuestro)
     y devolver la lista dinámica de marcas a buscar + el mapa de precios techo.
  2. Leer la tabla "Registro de Importadores" (Importador, Estado) y devolver
     un diccionario {importador_normalizado: estado}.
  3. Exponer `alta_importador_por_validar()` para insertar automáticamente
     un importador nuevo detectado en aduana con Estado = "POR_VALIDAR".

No hay marcas ni importadores hardcodeados: todo se descubre en runtime
consultando las bases de datos de Notion apuntadas por los IDs en las
variables de entorno.

Variables de entorno requeridas:
  NOTION_TOKEN                 -> token de integración interna de Notion
  NOTION_DATABASE_ID            -> ID de la base "Marcas Competidoras"
  NOTION_IMPORTADORES_DB_ID     -> ID de la base "Registro de Importadores"
                                   (opcional; si no se define, se asume que
                                   NOTION_DATABASE_ID apunta a un workspace
                                   donde ambas tablas comparten el mismo
                                   padre y se debe setear explícitamente)
"""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Tuple

import requests

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Nombres de columna esperados en Notion (ajustar aquí si el nombre difiere)
COL_MARCA_RIVAL = "Marca_Rival"
COL_PRECIO_TECHO = "Precio_Techo_Nuestro"
COL_MARCA_PROPIA = "Marca_Propia"  # a qué marca propia (COEL/SANHUA/VHM) le compite esta fila
COL_IMPORTADOR = "Importador"
COL_ESTADO = "Estado"

# Fallback si una fila de "Marcas Competidoras" no tiene Marca_Propia cargada
# en Notion (para no perder la fila silenciosamente).
MARCA_PROPIA_SIN_ASIGNAR = "SIN_ASIGNAR"

ESTADO_POR_VALIDAR = "POR_VALIDAR"
ESTADOS_VALIDOS = {"COMPETIDOR", "NO_COMPITE", "POR_VALIDAR", "CLIENTE"}


def _headers() -> dict:
    token = os.environ["NOTION_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _query_database(database_id: str) -> List[dict]:
    """Pagina sobre una base de datos de Notion y devuelve todas las filas (results)."""
    url = f"{NOTION_API_BASE}/databases/{database_id}/query"
    results: List[dict] = []
    payload: dict = {"page_size": 100}

    while True:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))

        if data.get("has_more"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return results


def _extract_plain_text(prop: dict) -> str:
    """Extrae texto plano de una propiedad Notion sin importar si es
    title, rich_text o select."""
    if not prop:
        return ""

    prop_type = prop.get("type")

    if prop_type == "title":
        parts = prop.get("title", [])
        return "".join(p.get("plain_text", "") for p in parts).strip()

    if prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(p.get("plain_text", "") for p in parts).strip()

    if prop_type == "select":
        sel = prop.get("select")
        return sel["name"].strip() if sel else ""

    if prop_type == "status":
        st = prop.get("status")
        return st["name"].strip() if st else ""

    if prop_type == "number":
        return prop.get("number")

    return ""


def _extract_number(prop: dict) -> float:
    if not prop:
        return 0.0
    if prop.get("type") == "number":
        return float(prop.get("number") or 0.0)
    # tolerar precio cargado como texto ("1234.56")
    val = _extract_plain_text(prop)
    try:
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def get_marcas_competidoras() -> Tuple[List[str], Dict[str, float], Dict[str, str]]:
    """
    Lee la tabla "Marcas Competidoras" y devuelve:
      - lista_marcas: ["CAREL", "DANFOSS", "ELITECH", "FULL GAUGE", ...]
      - precios_techo: {"CAREL": 123.45, "DANFOSS": 98.0, ...}
      - marca_propia_map: {"CAREL": "COEL", "DANFOSS": "SANHUA", ...}
        -> a qué marca propia (COEL/SANHUA/VHM) le compite cada rival.
        Si la fila no tiene 'Marca_Propia' cargada en Notion, se marca como
        "SIN_ASIGNAR" para poder detectarlo en el reporte en vez de perderla.

    100% dinámico: agregar una fila nueva en Notion (incluida una marca
    propia nueva) la incorpora en la próxima corrida sin tocar código.
    """
    database_id = os.environ["NOTION_DATABASE_ID"]
    rows = _query_database(database_id)

    marcas: List[str] = []
    precios: Dict[str, float] = {}
    marca_propia_map: Dict[str, str] = {}

    for row in rows:
        props = row.get("properties", {})
        marca_raw = _extract_plain_text(props.get(COL_MARCA_RIVAL))
        if not marca_raw:
            continue

        marca = marca_raw.strip().upper()
        precio = _extract_number(props.get(COL_PRECIO_TECHO))
        marca_propia_raw = _extract_plain_text(props.get(COL_MARCA_PROPIA))
        marca_propia = marca_propia_raw.strip().upper() if marca_propia_raw else MARCA_PROPIA_SIN_ASIGNAR

        marcas.append(marca)
        precios[marca] = precio
        marca_propia_map[marca] = marca_propia

    # dedupe preservando orden
    marcas_unicas = list(dict.fromkeys(marcas))

    logger.info("Marcas competidoras leídas de Notion: %s", marcas_unicas)
    return marcas_unicas, precios, marca_propia_map


def get_registro_importadores() -> Dict[str, str]:
    """
    Lee la tabla "Registro de Importadores" y devuelve:
      {"IMPORTADORA XYZ SA": "COMPETIDOR", "CLIENTE ABC": "CLIENTE", ...}

    Las claves quedan normalizadas en mayúsculas y sin espacios extra para
    facilitar el cruce con los datos de aduana.
    """
    database_id = os.environ.get(
        "NOTION_IMPORTADORES_DB_ID", os.environ["NOTION_DATABASE_ID"]
    )
    rows = _query_database(database_id)

    registro: Dict[str, str] = {}
    for row in rows:
        props = row.get("properties", {})
        importador_raw = _extract_plain_text(props.get(COL_IMPORTADOR))
        estado_raw = _extract_plain_text(props.get(COL_ESTADO))

        if not importador_raw:
            continue

        importador = " ".join(importador_raw.split()).upper()
        estado = (estado_raw or ESTADO_POR_VALIDAR).strip().upper()

        if estado not in ESTADOS_VALIDOS:
            logger.warning(
                "Estado desconocido '%s' para importador '%s'; se usa POR_VALIDAR",
                estado, importador,
            )
            estado = ESTADO_POR_VALIDAR

        registro[importador] = estado

    logger.info("Registro de importadores leído: %d filas", len(registro))
    return registro


def alta_importador_por_validar(nombre_importador: str) -> None:
    """
    Inserta (POST) un nuevo importador en la tabla "Registro de Importadores"
    con Estado = POR_VALIDAR. Se llama automáticamente cuando el analizador
    encuentra un importador que no existe en Notion.
    """
    database_id = os.environ.get(
        "NOTION_IMPORTADORES_DB_ID", os.environ["NOTION_DATABASE_ID"]
    )
    nombre = " ".join(nombre_importador.split()).upper()

    url = f"{NOTION_API_BASE}/pages"
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            COL_IMPORTADOR: {
                "title": [{"text": {"content": nombre}}]
            },
            COL_ESTADO: {
                "select": {"name": ESTADO_POR_VALIDAR}
            },
        },
    }

    resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
    if resp.status_code >= 300:
        logger.error(
            "Fallo al dar de alta '%s' en Notion: %s - %s",
            nombre, resp.status_code, resp.text,
        )
        resp.raise_for_status()

    logger.info("Importador nuevo dado de alta en Notion como POR_VALIDAR: %s", nombre)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    marcas, precios, marca_propia_map = get_marcas_competidoras()
    print("Marcas:", marcas)
    print("Precios techo:", precios)
    print("Marca propia por rival:", marca_propia_map)
    print("Importadores:", get_registro_importadores())
