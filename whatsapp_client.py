"""
whatsapp_client.py
===================
Módulo 4 — Despachador de Alertas WhatsApp.

Envía UN ÚNICO mensaje resumen mensual al celular configurado, usando una
API HTTP genérica de WhatsApp (ej. WhatsApp Business Cloud API, Twilio,
CallMeBot, o cualquier gateway compatible con WA_API_URL + WA_TOKEN).

El mensaje se arma a partir del resumen numérico que produce el Módulo 3
(analyzer.run()): alertas_fuga, alertas_precio, nuevos_hallazgos.

Variables de entorno requeridas:
  WA_API_URL   -> endpoint HTTP del gateway de WhatsApp
  WA_TOKEN     -> token/clave de autenticación del gateway
  WA_CELULAR   -> número de celular destino (formato internacional, ej. 5491122334455)
"""

from __future__ import annotations

import datetime
import logging
import os

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DASHBOARD_URL = os.environ.get("STREAMLIT_DASHBOARD_URL", "https://tu-app.streamlit.app")


def _mes_anterior_es() -> str:
    hoy = datetime.date.today()
    primer_dia_mes_actual = hoy.replace(day=1)
    ultimo_dia_mes_anterior = primer_dia_mes_actual - datetime.timedelta(days=1)

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    return f"{meses[ultimo_dia_mes_anterior.month - 1]} {ultimo_dia_mes_anterior.year}"


def construir_mensaje(resumen: dict) -> str:
    """Arma el texto del mensaje consolidado a partir del resumen del Módulo 3."""
    alertas_fuga = resumen.get("alertas_fuga", 0)
    alertas_precio = resumen.get("alertas_precio", 0)
    nuevos_hallazgos = resumen.get("nuevos_hallazgos", 0)
    desglose = resumen.get("desglose_por_marca_propia", {})

    lineas_desglose = ""
    if desglose:
        marcas_ordenadas = sorted(desglose.keys())
        filas = [
            f"   • *{marca}*: {datos.get('alertas_fuga', 0)} fuga / {datos.get('alertas_precio', 0)} precio"
            for marca, datos in ((m, desglose[m]) for m in marcas_ordenadas)
        ]
        lineas_desglose = "\n📌 *Desglose por marca propia:*\n" + "\n".join(filas) + "\n"

    return (
        "🔔 *RESUMEN MENSUAL: RADAR DE MARCAS COMPETIDORAS*\n"
        "--------------------------------------------------\n"
        f"🕒 _Período Analizado: {_mes_anterior_es()}_\n\n"
        f"🚨 *ALERTAS DE FUGA:* Se detectaron {alertas_fuga} clientes propios "
        "comprando directo a marcas rivales (Carel/Danfoss/Full Gauge).\n\n"
        f"📉 *PRESIÓN DE PRECIOS:* Se detectaron {alertas_precio} operaciones "
        "de la competencia rompiendo tus precios de referencia establecidos en Notion.\n\n"
        f"🕵️‍♂️ *NUEVOS COMPETIDORES:* Se descubrieron {nuevos_hallazgos} nuevas "
        "empresas importando estas marcas. Ya están cargadas automáticamente en "
        "Notion esperando tu validación mensual.\n"
        f"{lineas_desglose}\n"
        f"📊 _Ingresa al Dashboard de Streamlit para auditar las marcas de la "
        f"competencia de manera detallada:_\n{DASHBOARD_URL}"
    )


def enviar_resumen_whatsapp(resumen: dict) -> bool:
    """
    Envía el mensaje consolidado. Devuelve True si el gateway respondió OK.

    El payload sigue el formato genérico {to, message, token} — si tu
    gateway específico (Twilio, Meta Cloud API, CallMeBot, etc.) espera un
    esquema distinto, ajustar únicamente esta función.
    """
    wa_api_url = os.environ["WA_API_URL"]
    wa_token = os.environ["WA_TOKEN"]
    wa_celular = os.environ["WA_CELULAR"]

    mensaje = construir_mensaje(resumen)

    payload = {
        "to": wa_celular,
        "message": mensaje,
    }
    headers = {
        "Authorization": f"Bearer {wa_token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(wa_api_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Fallo al enviar el mensaje de WhatsApp.")
        return False

    logger.info("Mensaje de WhatsApp enviado correctamente a %s", wa_celular)
    return True


if __name__ == "__main__":
    resumen_demo = {
        "alertas_fuga": 2, "alertas_precio": 5, "nuevos_hallazgos": 3,
        "desglose_por_marca_propia": {
            "COEL": {"alertas_fuga": 1, "alertas_precio": 3},
            "SANHUA": {"alertas_fuga": 1, "alertas_precio": 1},
            "VHM": {"alertas_fuga": 0, "alertas_precio": 1},
        },
    }
    print(construir_mensaje(resumen_demo))
