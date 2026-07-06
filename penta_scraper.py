"""
penta_scraper.py
================
Módulo 2 — Extractor Automatizado por Marca (Playwright, sync API).

Flujo:
  1. Trae la lista dinámica de marcas desde Notion (Módulo 1).
  2. Inicia sesión en Penta-Transaction con PENTA_USER / PENTA_PASS.
  3. Para cada marca:
       - Va al buscador.
       - Completa el campo 'Marca/Fabricante'.
       - Clic en 'Buscar'.
       - Espera a que la tabla de resultados cargue.
       - Clic en 'Exportar a Excel' capturando el evento de descarga.
       - Guarda el archivo como downloads/datos_{marca}.xlsx.

Diseñado para correr headless en GitHub Actions. Los selectores están
marcados con comentarios "AJUSTAR SELECTOR" para adaptarlos rápido si
Penta cambia su DOM.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import List

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from notion_client import get_marcas_competidoras

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PENTA_LOGIN_URL = "https://www.penta-transaction.com/login"  # AJUSTAR: URL real de login
PENTA_BUSCADOR_URL = "https://www.penta-transaction.com/search"  # AJUSTAR: URL real del buscador

DOWNLOAD_DIR = Path("downloads")
DEFAULT_TIMEOUT_MS = 30_000


def _sanitizar_nombre(marca: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", marca.strip())


def login(page) -> None:
    """Inicia sesión en Penta-Transaction usando credenciales de entorno."""
    penta_user = os.environ["PENTA_USER"]
    penta_pass = os.environ["PENTA_PASS"]

    logger.info("Iniciando sesión en Penta-Transaction...")
    page.goto(PENTA_LOGIN_URL, wait_until="domcontentloaded")

    # AJUSTAR SELECTOR: campo de usuario
    page.fill("#username", penta_user)
    # AJUSTAR SELECTOR: campo de contraseña
    page.fill("#password", penta_pass)
    # AJUSTAR SELECTOR: botón de login
    page.click("button[type='submit']")

    # Esperar a que la sesión quede establecida (ej. aparición de un elemento
    # del dashboard post-login). AJUSTAR SELECTOR según la app real.
    page.wait_for_selector("text=Buscador", timeout=DEFAULT_TIMEOUT_MS)
    logger.info("Login exitoso.")


def buscar_y_exportar_marca(page, marca: str) -> Path | None:
    """
    Busca una marca puntual en el buscador de Penta y exporta el resultado
    a Excel. Devuelve el path del archivo guardado, o None si falló.
    """
    logger.info("Procesando marca: %s", marca)
    page.goto(PENTA_BUSCADOR_URL, wait_until="domcontentloaded")

    # AJUSTAR SELECTOR: input de "Marca/Fabricante" del buscador Penta.
    # Ejemplos típicos según la plataforma:
    #   page.fill("input[name='marca_fabricante']", marca)
    #   page.fill("#txtMarca", marca)
    campo_marca_selector = "input[name='marca_fabricante']"
    page.wait_for_selector(campo_marca_selector, timeout=DEFAULT_TIMEOUT_MS)
    page.fill(campo_marca_selector, "")
    page.fill(campo_marca_selector, marca)

    # AJUSTAR SELECTOR: botón "Buscar"
    boton_buscar_selector = "button#btnBuscar"
    page.click(boton_buscar_selector)

    # Esperar la carga de la tabla de resultados.
    # AJUSTAR SELECTOR: contenedor/tabla de resultados de búsqueda.
    tabla_resultados_selector = "table#resultados-busqueda"
    try:
        page.wait_for_selector(tabla_resultados_selector, timeout=DEFAULT_TIMEOUT_MS)
    except PWTimeoutError:
        logger.warning("Sin resultados (o timeout) para marca '%s'. Se omite.", marca)
        return None

    # Si la tabla existe pero está vacía, evitar exportar un archivo inútil.
    filas = page.query_selector_all(f"{tabla_resultados_selector} tbody tr")
    if not filas:
        logger.warning("Tabla de resultados vacía para marca '%s'. Se omite.", marca)
        return None

    # AJUSTAR SELECTOR: botón "Exportar a Excel"
    boton_exportar_selector = "button#btnExportarExcel"

    nombre_archivo = f"datos_{_sanitizar_nombre(marca)}.xlsx"
    destino = DOWNLOAD_DIR / nombre_archivo

    with page.expect_download(timeout=DEFAULT_TIMEOUT_MS) as download_info:
        page.click(boton_exportar_selector)
    download = download_info.value
    download.save_as(str(destino))

    logger.info("Exportado: %s", destino)
    return destino


def run(marcas_override: List[str] | None = None) -> List[Path]:
    """
    Orquesta el scraping completo. Devuelve la lista de paths descargados.

    marcas_override permite forzar una lista de marcas puntual (útil para
    tests locales) sin tener que pasar por Notion.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if marcas_override is not None:
        marcas = marcas_override
    else:
        marcas, _precios, _marca_propia_map = get_marcas_competidoras()

    if not marcas:
        logger.warning("No se encontraron marcas en Notion. Nada que scrapear.")
        return []

    archivos_descargados: List[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            login(page)

            for marca in marcas:
                try:
                    archivo = buscar_y_exportar_marca(page, marca)
                    if archivo:
                        archivos_descargados.append(archivo)
                except Exception:
                    logger.exception("Error procesando la marca '%s'. Se continúa con la siguiente.", marca)
                # Pausa breve entre marcas para no saturar el sitio /
                # simular comportamiento humano.
                time.sleep(2)

        finally:
            context.close()
            browser.close()

    logger.info("Scraping finalizado. Archivos descargados: %d", len(archivos_descargados))
    return archivos_descargados


if __name__ == "__main__":
    run()
