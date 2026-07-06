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

PENTA_LOGIN_URL = "https://app.penta-transaction.com/login/es"
PENTA_BUSCADOR_URL = "https://app.penta-transaction.com/home/formulario/AR/importDetalladas"

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
    page.fill("#inputUsuario", penta_user)
    # AJUSTAR SELECTOR: campo de contraseña — <p-password id="inputPassword"> es un
    # wrapper de PrimeNG; el <input type="password"> real está anidado adentro.
    page.fill("p-password#inputPassword input", penta_pass)
    # AJUSTAR SELECTOR: botón de login (componente <ion-button type="submit"> con texto "Ingresar")
    page.click("ion-button:has-text('Ingresar')")

    # Esperar a que la sesión quede establecida: la URL deja de contener
    # "/login" una vez que el login es exitoso.
    page.wait_for_url(lambda url: "/login" not in url, timeout=DEFAULT_TIMEOUT_MS)
    logger.info("Login exitoso.")


def buscar_y_exportar_marca(page, marca: str) -> Path | None:
    """
    Busca una marca puntual en el buscador de Penta y exporta el resultado
    a Excel. Devuelve el path del archivo guardado, o None si falló.
    """
    logger.info("Procesando marca: %s", marca)
    page.goto(PENTA_BUSCADOR_URL, wait_until="domcontentloaded")

    # AJUSTAR SELECTOR: el campo "Marca" es un buscador tipo Ionic (ion-searchbar)
    # que abre una lista filtrada de opciones al escribir. El "name" con índice
    # numérico (ion-searchbar-2) puede variar si cambia el orden de los campos
    # en el formulario; si falla, volver a inspeccionar y ajustar.
    campo_marca_selector = "input.searchbar-input[placeholder='Buscar']"
    page.wait_for_selector(campo_marca_selector, timeout=DEFAULT_TIMEOUT_MS)
    page.click(campo_marca_selector)
    page.fill(campo_marca_selector, marca)

    # Esperar a que aparezca la lista filtrada y clickear la opción que
    # coincide exactamente con la marca buscada.
    # AJUSTAR SELECTOR: ajustar el contenedor de la lista de opciones si el
    # texto no matchea (mayúsculas/acentos) o si el ítem no es clickeable
    # directo (a veces hay un checkbox al lado del texto).
    try:
        opcion_selector = f"text='{marca}'"
        page.wait_for_selector(opcion_selector, timeout=DEFAULT_TIMEOUT_MS)
        page.click(opcion_selector)
    except PWTimeoutError:
        logger.warning("No apareció la opción '%s' en el listado de marcas. Se omite.", marca)
        return None

    # AJUSTAR SELECTOR: botón "Buscar" (botón azul con ícono de lupa)
    boton_buscar_selector = "ion-button:has-text('Buscar'), button:has-text('Buscar')"
    page.click(boton_buscar_selector)

    # Esperar la carga de la tabla de resultados (headers "Fecha"/"País de Origen").
    # AJUSTAR SELECTOR: si la grilla usa virtual-scroll y tarda en pintar filas,
    # puede hacer falta esperar también un ícono/spinner de carga a que desaparezca.
    tabla_resultados_selector = "text='País de Origen'"
    try:
        page.wait_for_selector(tabla_resultados_selector, timeout=DEFAULT_TIMEOUT_MS)
    except PWTimeoutError:
        logger.warning("Sin resultados (o timeout) para marca '%s'. Se omite.", marca)
        return None

    # Si no hay filas de datos (solo el header), evitar exportar un archivo vacío.
    filas = page.query_selector_all("text=/^\\d{1,2}\\/\\d{1,2}\\/\\d{4}$/")
    if not filas:
        logger.warning("Tabla de resultados vacía para marca '%s'. Se omite.", marca)
        return None

    # AJUSTAR SELECTOR: botón "Exportar a Excel" — ícono con alt="Descargar Excel"
    # dentro de la sección "Descargas" del panel lateral izquierdo.
    boton_exportar_selector = "img[alt='Descargar Excel']"

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
