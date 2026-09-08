# Verificación del editor

- 12 pruebas unitarias: aprobadas.
- API local: fórmula, CSV con tiempos y nodos, aprobadas.
- Exportación ZIP por API: integridad, número de muestras, RMS y metadatos, aprobados.
- Solicitud sin token válido rechazada (HTTP 403).
- Vista reducida conserva un pulso de una muestra en una tabla de 131 072 puntos.
- Cálculo de esa tabla y vista previa: 0.78 s en esta PC (una ejecución).
- Interfaz revisada en navegador: gráfico seno, rechazo por rango, normalización y descarga ZIP.
- Ejemplo_SENO_1Hz_USB.zip: seno simulado de 4096 puntos; 1 Hz, escala 1 Vpp, offset 0, carga prevista High Z.
- Validación física TFW en AFG1062: exitosa, confirmada por Marcelo Valdéz. Las comprobaciones de software no conectan ni controlan el instrumento.
