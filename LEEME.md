# Editor local de formas de onda para AFG1062

Abrir **Iniciar.cmd** con doble clic. Se abre el navegador con el editor servido por Python en `127.0.0.1`. No requiere administrador, Tkinter, pip, Internet, VISA ni controladores. Requiere Python 3.10 o posterior; el lanzador usa el Python 3.12 existente en esta PC y, como alternativa, `python` del PATH.

Para finalizar, pulsar **Cerrar editor**. Cerrar solo la pestaña no detiene Python; también puede detenerse con Ctrl+C en su consola.

## Flujo de trabajo

1. Elegir fórmula, nodos lineales o CSV; definir N y período T.
2. Ajustar Vpp, offset y carga para la vista previa y las instrucciones de configuración manual.
3. Generar vista previa. Todo cambio en la señal invalida la exportación hasta recalcular.
4. Descargar el paquete ZIP y extraerlo. Copiar **ONDA.tfw** al pendrive; conservar **AJUSTES.txt**.
5. En el equipo: **Arb → Others → File browse → USBDEVICE → Enter**. Seleccionar el archivo y seguir el menú del firmware para cargarlo en una memoria de usuario.
6. Configurar la frecuencia de repetición, amplitud, offset y carga según AJUSTES.txt. Verificar con osciloscopio antes de utilizar la señal en un ensayo.

La aplicación no accede a los instrumentos, no activa salidas y no escribe directamente en el pendrive. El navegador descarga el ZIP en su carpeta habitual o en la ubicación elegida por el usuario.

## Definición de la señal

- `u=t/T`; las muestras se toman en `u=i/N`, con `i=0..N−1`. T no se duplica: esto es una tabla para reproducción periódica.
- `sin(2*pi*u)` contiene un ciclo por registro. `sin(2*pi*5*u)` contiene cinco; su frecuencia sinusoidal será cinco veces la frecuencia de repetición del registro.
- Se admiten `t`, `T`, `pi`, `e`, operaciones aritméticas, `**`, funciones matemáticas y condicionales, por ejemplo `1 if u < 0.25 else -1`. Se interpreta un árbol restringido; no se ejecuta código Python arbitrario.
- Las fórmulas y CSV representan y normalizada. Sin normalización, cada valor debe estar entre −1 y +1. La normalización divide por el máximo absoluto: no elimina la continua y no recorta.
- Nodos: dos columnas `u,y`, ordenadas estrictamente, desde u=0 a u=1; interpolación lineal.
- CSV: una columna y, o dos columnas t,y. Los tiempos deben estar en segundos, ser crecientes y uniformes. En dos columnas se usa `T=N·Δt`, ignorando el período del formulario. El origen temporal se traslada a cero. No hay remuestreo automático. Un CSV que ya incluye ambos extremos de un ciclo debe prepararse eliminando la muestra final duplicada antes de importarlo.
- Separadores: coma, punto y coma o tabulación. Con punto y coma o tabulación puede usarse coma decimal. Encabezado opcional mediante casilla explícita.
- Límite conservador de esta aplicación: 2 a 131 072 muestras, no el máximo anunciado del equipo. N/T debe ser ≤300 MS/s; es una tasa equivalente de la tabla, no una afirmación sobre el reloj DAC interno.
- Vista previa tras cuantización de 14 bits: `V=offset + Vpp·y/2`. La amplitud de salida real depende de la carga y configuración del generador; los límites eléctricos deben verificarse en el AFG1062.
- La vista preserva mínimos y máximos de bloques al reducir puntos para pantalla; no es una simulación de la respuesta analógica del generador. La línea punteada indica el cierre periódico.

## Estado del formato TFW

**La compatibilidad física de los archivos generados está pendiente de prueba en el AFG1062.**

El código implementa la estructura identificada en el ejemplo de lectura publicado por Tektronix: cabecera de 512 bytes, identificador TEKAFG3000, versión 20050114, cantidad de puntos y datos de 16 bits sin signo en orden big-endian. Los códigos usados son de 14 bits, 0..16383.

La exportación predeterminada usa una **cabecera mínima experimental**: pone en cero los campos de cabecera que el ejemplo no describe. No se afirma que esta cabecera sea una especificación oficial de escritura ni que todos los firmwares la acepten.

Como alternativa, se puede cargar una plantilla TFW válida guardada por ArbExpress o por un instrumento. Debe tener exactamente el mismo N, identificador y versión admitidos. Se conserva su cabecera completa y se reemplazan solo las muestras. Si contiene una miniatura, será la anterior. Tampoco se garantiza aceptación sin prueba en el equipo.

El TFW no contiene frecuencia, amplitud ni offset. No renombrar un CSV a TFW: son formatos diferentes.

## Archivos del paquete exportado

- ONDA.tfw: tabla de muestras para probar en el equipo.
- AJUSTES.txt: instrucciones y configuración manual.
- DATOS.csv: tiempo, valores normalizados, códigos DAC y tensión prevista. Es un archivo de auditoría de cuatro columnas; para reimportarlo en el editor seleccionar/preparar las dos primeras columnas, o abrir PROYECTO.json.
- PROYECTO.json: definición editable (no incluye el archivo de plantilla).
- METADATOS.json: muestreo, normalización y cuantización.

## Fuentes técnicas consultadas

- [Ejemplo TFW de Tektronix](https://github.com/tektronix/Programmatic-Control-Examples/blob/master/Examples/Signal_Sources/src/AfgTfwExample/AfgTFW_example.py): estructura binaria leída; ejemplo para AFG3000.
- [Notas oficiales AFG1062](https://download.tek.com/software/supporting_files/AFG1062_V1.1.0_Release_Notes_066178108.pdf): carga de ondas .tfw desde USB.
- [FAQ de Tektronix sobre TFS/TFW](https://www.tek.com/fr/support/faqs/what-difference-between-afg3000s-tfs-and-tfw-files): ausencia de ajustes eléctricos y temporales; formato propietario, sin especificación oficial pública.
- [Controlador abierto AFG1000/AFG3000](https://github.com/asvela/tektronix-func-gen): rango de códigos de 14 bits.

## Pruebas reproducibles

Desde esta carpeta: `python -m unittest -v test_waveform.py`.
Las pruebas comprueban cálculo, cuantización, validación de entradas, integridad binaria y paquetes. No sustituyen la carga real ni una verificación metrológica.
