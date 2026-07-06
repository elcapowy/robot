"""
generar_datos_prueba.py
=======================
Utilidad de testing local: genera un 'reporte_marcas_mensual.xlsx' con datos
de ejemplo (mismas 4 hojas que produce analyzer.py) para poder correr
`streamlit run app.py` sin depender de Penta ni Notion.

Uso:
    python generar_datos_prueba.py
    streamlit run app.py
"""

from pathlib import Path

from analyzer import (
    ResultadoAnalisis,
    generar_reporte_excel,
)

resultado = ResultadoAnalisis(
    filas_validas=[
        {"Importador": "FRIOTEC IMPORTACIONES SA", "Marca": "CAREL", "Producto": "Controlador electrónico C1",
         "Precio_Unitario_FOB": 88.50, "Cantidad": 500, "Estado_Importador": "COMPETIDOR",
         "Marca_Propia_Afectada": "COEL"},
        {"Importador": "FRIOTEC IMPORTACIONES SA", "Marca": "DANFOSS", "Producto": "Válvula solenoide",
         "Precio_Unitario_FOB": 45.00, "Cantidad": 300, "Estado_Importador": "COMPETIDOR",
         "Marca_Propia_Afectada": "SANHUA"},
        {"Importador": "CLIMA SUR SRL", "Marca": "FULL GAUGE", "Producto": "Termostato digital",
         "Precio_Unitario_FOB": 22.30, "Cantidad": 1200, "Estado_Importador": "CLIENTE",
         "Marca_Propia_Afectada": "VHM"},
        {"Importador": "REFRIARGENTINA SA", "Marca": "ELITECH", "Producto": "Sensor de temperatura",
         "Precio_Unitario_FOB": 12.80, "Cantidad": 800, "Estado_Importador": "POR_VALIDAR",
         "Marca_Propia_Afectada": "COEL"},
        {"Importador": "NUEVA FRIA IMPORT SA", "Marca": "CAREL", "Producto": "Controlador electrónico C2",
         "Precio_Unitario_FOB": 95.00, "Cantidad": 150, "Estado_Importador": "POR_VALIDAR",
         "Marca_Propia_Afectada": "COEL"},
    ],
    alertas_fuga=[
        {"Importador": "CLIMA SUR SRL", "Marca": "FULL GAUGE", "Producto": "Termostato digital",
         "Precio_Unitario_FOB": 22.30, "Cantidad": 1200, "Tipo_Alerta": "🚨 Alerta Urgente de Pérdida de Cliente",
         "Marca_Propia_Afectada": "VHM"},
    ],
    alertas_precio=[
        {"Importador": "FRIOTEC IMPORTACIONES SA", "Marca": "CAREL", "Producto": "Controlador electrónico C1",
         "Precio_Unitario_FOB": 88.50, "Precio_Techo_Nuestro": 120.00, "Umbral_Alerta": 96.00,
         "Tipo_Alerta": "📉 Alerta de Competencia por Precio Bajo", "Marca_Propia_Afectada": "COEL"},
        {"Importador": "FRIOTEC IMPORTACIONES SA", "Marca": "DANFOSS", "Producto": "Válvula solenoide",
         "Precio_Unitario_FOB": 45.00, "Precio_Techo_Nuestro": 95.50, "Umbral_Alerta": 76.40,
         "Tipo_Alerta": "📉 Alerta de Competencia por Precio Bajo", "Marca_Propia_Afectada": "SANHUA"},
    ],
    nuevos_hallazgos=["REFRIARGENTINA SA", "NUEVA FRIA IMPORT SA"],
)

if __name__ == "__main__":
    salida = generar_reporte_excel(resultado, Path("reporte_marcas_mensual.xlsx"))
    print(f"Reporte de prueba generado en: {salida.resolve()}")
    print("Ahora corré: streamlit run app.py")
