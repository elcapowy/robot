"""
main.py
=======
Orquestador principal: encadena los 4 módulos en el orden correcto.
Este es el script que dispara GitHub Actions una vez al mes.

Orden de ejecución:
  1. penta_scraper.run()  -> trae marcas de Notion y descarga datos_{marca}.xlsx
  2. analyzer.run()       -> analiza, cruza contra Notion, genera el reporte y
                             las altas automáticas de importadores nuevos
  3. whatsapp_client.enviar_resumen_whatsapp(resumen) -> un único mensaje mensual
"""

from __future__ import annotations

import logging
import sys

import analyzer
import penta_scraper
import whatsapp_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("=== Iniciando corrida mensual: Radar de Marcas Competidoras ===")

    try:
        archivos = penta_scraper.run()
        logger.info("Scraping completado: %d archivos descargados.", len(archivos))
    except Exception:
        logger.exception("Falló el Módulo 2 (scraper). Se aborta la corrida.")
        return 1

    try:
        resumen = analyzer.run()
        logger.info("Análisis completado: %s", resumen)
    except Exception:
        logger.exception("Falló el Módulo 3 (analyzer). Se aborta la corrida.")
        return 1

    try:
        enviado = whatsapp_client.enviar_resumen_whatsapp(resumen)
        if not enviado:
            logger.error("El envío de WhatsApp no se confirmó correctamente.")
    except Exception:
        logger.exception("Falló el Módulo 4 (WhatsApp). El reporte ya quedó generado.")
        return 1

    logger.info("=== Corrida mensual finalizada con éxito ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
