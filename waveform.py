"""Waveform math and TFW codec; Python standard library only."""
import ast
import base64
import csv
import io
import math
import struct
import zipfile
import json

MAX_POINTS = 1_000_000  # application sample limit
MAGIC = b'TEKAFG3000'
VERSION = 20050114
FUNCS = {n: getattr(math, n) for n in ('sin', 'cos', 'tan', 'exp', 'sqrt', 'log', 'log10', 'floor', 'ceil', 'tanh', 'asin', 'acos', 'atan')}
FUNCS.update(abs=abs, min=min, max=max)


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Todos los valores deben ser finitos.')
    return result


def expression(source):
    if len(source) > 1000:
        raise ValueError('La fórmula es demasiado larga.')
    tree = ast.parse(source, mode='eval')
    if len(list(ast.walk(tree))) > 160:
        raise ValueError('La fórmula es demasiado compleja.')
    allowed = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp,
               ast.UnaryOp, ast.Call, ast.Add, ast.Sub, ast.Mult, ast.Div,
               ast.Pow, ast.Mod, ast.UAdd, ast.USub, ast.Compare, ast.Lt,
               ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq, ast.IfExp)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError('Operación no permitida en la fórmula.')
        if isinstance(node, ast.Name) and node.id not in {'u', 't', 'T', 'pi', 'e'} | FUNCS.keys():
            raise ValueError('Nombre desconocido: ' + node.id)
        if isinstance(node, ast.Constant) and (type(node.value) not in (int, float) or abs(node.value) > 1e100):
            raise ValueError('Constante no válida.')
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in FUNCS or node.keywords or len(node.args) > 4):
            raise ValueError('Función no permitida.')

    def run(node, env):
        if isinstance(node, ast.Expression): return run(node.body, env)
        if isinstance(node, ast.Constant): return float(node.value)
        if isinstance(node, ast.Name): return env[node.id]
        if isinstance(node, ast.UnaryOp):
            v = run(node.operand, env)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.IfExp): return run(node.body if run(node.test, env) else node.orelse, env)
        if isinstance(node, ast.Compare):
            a = run(node.left, env)
            for op, right in zip(node.ops, node.comparators):
                b = run(right, env)
                ok = {ast.Lt: lambda: a < b, ast.LtE: lambda: a <= b,
                      ast.Gt: lambda: a > b, ast.GtE: lambda: a >= b,
                      ast.Eq: lambda: a == b, ast.NotEq: lambda: a != b}[type(op)]()
                if not ok: return False
                a = b
            return True
        if isinstance(node, ast.Call): return FUNCS[node.func.id](*(run(a, env) for a in node.args))
        a, b = run(node.left, env), run(node.right, env)
        if isinstance(node.op, ast.Pow):
            if abs(b) > 100: raise ValueError('Exponente fuera de ±100.')
            return number(a ** b)
        return number({ast.Add: lambda: a+b, ast.Sub: lambda: a-b,
                       ast.Mult: lambda: a*b, ast.Div: lambda: a/b,
                       ast.Mod: lambda: a % b}[type(node.op)]())
    return lambda u, T: number(run(tree, dict(u=u, t=u*T, T=T, pi=math.pi, e=math.e)))


def read_columns(text, delimiter=',', skip_header=False):
    if delimiter not in (',', ';', '\t'): raise ValueError('Separador no válido.')
    rows = list(csv.reader(io.StringIO(text.lstrip('\ufeff')), delimiter=delimiter))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if skip_header: rows = rows[1:]
    if not 2 <= len(rows) <= MAX_POINTS: raise ValueError(f'Se necesitan entre 2 y {MAX_POINTS} filas de datos.')
    width = len(rows[0])
    if width not in (1, 2) or any(len(r) != width for r in rows):
        raise ValueError('Use una columna y, o dos columnas t,y; todas las filas deben tener igual tamaño.')
    # Decimal comma is only unambiguous with semicolon/tab separators.
    return [[number(c.strip().replace(',', '.') if delimiter != ',' else c.strip()) for c in r] for r in rows]


def build(spec):
    T = number(spec.get('period', 1))
    if not 1/30e6 <= T <= 1e6: raise ValueError('El período debe estar entre 1/30 MHz y 1 000 000 s.')
    mode = spec.get('mode', 'formula')
    if mode == 'csv':
        rows = read_columns(spec.get('csv', ''), spec.get('delimiter', ','), spec.get('header', False))
        y = [r[-1] for r in rows]
        n = len(y)
        if len(rows[0]) == 2:
            dt = rows[1][0] - rows[0][0]
            if dt <= 0: raise ValueError('El tiempo debe crecer estrictamente.')
            if any(not math.isclose(rows[i][0]-rows[i-1][0], dt, rel_tol=1e-5, abs_tol=abs(dt)*1e-7) for i in range(2,n)):
                raise ValueError('Los tiempos no son uniformes. Remuestree los datos antes de importar.')
            T = n * dt
            if not 1/30e6 <= T <= 1e6: raise ValueError('El período derivado del CSV está fuera de rango.')
    else:
        n0 = number(spec.get('points', 4096))
        n = int(n0)
        if n != n0 or not 2 <= n <= MAX_POINTS: raise ValueError(f'N debe ser un entero entre 2 y {MAX_POINTS}.')
        if mode == 'formula':
            f = expression(spec.get('formula', 'sin(2*pi*u)'))
            y = [f(i/n, T) for i in range(n)]
        elif mode == 'nodes':
            nodes = read_columns(spec.get('nodes', ''), ',')
            if any(len(r) != 2 for r in nodes) or nodes[0][0] != 0 or nodes[-1][0] != 1:
                raise ValueError('Los nodos deben ser pares u,y y comenzar en u=0 y terminar en u=1.')
            if any(nodes[i][0] <= nodes[i-1][0] for i in range(1,len(nodes))): raise ValueError('Los nodos u deben crecer estrictamente.')
            y, j = [], 0
            for i in range(n):
                u = i/n
                while j+1 < len(nodes)-1 and u > nodes[j+1][0]: j += 1
                a, b = nodes[j], nodes[j+1]
                y.append(a[1] + (b[1]-a[1])*(u-a[0])/(b[0]-a[0]))
        else: raise ValueError('Modo desconocido.')
    original_min, original_max = min(y), max(y)
    scale = max(abs(original_min), abs(original_max))
    if spec.get('normalize', False) and scale > 0: y = [v/scale for v in y]
    if min(y) < -1 or max(y) > 1: raise ValueError('La señal excede [-1,1]. Active normalización o corrija los valores. No se recorta automáticamente.')
    if n/T > 300e6: raise ValueError('N/T supera 300 MS/s. Aumente el período o reduzca N.')
    vpp, offset = number(spec.get('vpp', 1)), number(spec.get('offset', 0))
    if vpp <= 0: raise ValueError('Vpp debe ser positivo.')
    # 14-bit unsigned codes, same range as the AFG1000 driver. No implicit DC removal.
    codes = [int(math.floor((v+1)*16383/2+0.5)) for v in y]
    actual = [2*c/16383-1 for c in codes]
    meta = dict(points=n, period_s=T, repeat_hz=1/T, sample_interval_s=T/n,
                equivalent_sample_rate=n/T, vpp_setting=vpp, offset_setting=offset,
                load=spec.get('load', 'High Z'), min_normalized=min(y), max_normalized=max(y),
                source_min=original_min, source_max=original_max,
                normalization_divisor=scale if spec.get('normalize') and scale else 1,
                rms_normalized=math.sqrt(sum(v*v for v in y)/n),
                mean_normalized=sum(y)/n, seam_step=actual[0]-actual[-1],
                quantization_max_error=max(abs(a-b) for a,b in zip(y,actual)),
                hardware_validation='Validación física exitosa en AFG1062, confirmada por el usuario',
                sampling='t[i]=i*T/N, i=0..N-1. El extremo T no se duplica.')
    return y, codes, meta


def parse_tfw(blob):
    if len(blob) < 516 or blob[:16].rstrip(b'\0') != MAGIC: raise ValueError('Cabecera TFW TEKAFG3000 no reconocida.')
    version, n = struct.unpack_from('>II', blob, 16)
    if version != VERSION or not 2 <= n <= MAX_POINTS or len(blob) != 512+2*n:
        raise ValueError('Versión, cantidad de puntos o longitud TFW no admitida.')
    codes = list(struct.unpack_from(f'>{n}H', blob, 512))
    if max(codes) > 16383: raise ValueError('El archivo contiene valores fuera de 14 bits.')
    return codes


def encode_tfw(codes, template=None):
    if not 2 <= len(codes) <= MAX_POINTS or any(type(c) != int or not 0 <= c <= 16383 for c in codes):
        raise ValueError('Datos DAC inválidos.')
    if template:
        old = parse_tfw(template)
        if len(old) != len(codes): raise ValueError(f'La plantilla tiene {len(old)} puntos: use exactamente esa cantidad.')
        header = template[:512]
    else:
        header = bytearray(512)
        header[:len(MAGIC)] = MAGIC
        struct.pack_into('>II', header, 16, VERSION, len(codes))
    return bytes(header) + struct.pack(f'>{len(codes)}H', *codes)


def package(spec, template=None):
    y, codes, meta = build(spec)
    tfw = encode_tfw(codes, template)
    assert parse_tfw(tfw) == codes
    meta['tfw_header'] = 'Plantilla existente; cabecera conservada (miniatura puede ser antigua)' if template else 'Cabecera mínima; campos restantes en cero'
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['t_s', 'y_normalized', 'dac_14bit', 'voltage_preview_V'])
    for i, (v,c) in enumerate(zip(y,codes)):
        writer.writerow([format(i*meta['sample_interval_s'], '.15g'), format(v,'.15g'), c,
                         format(meta['offset_setting']+meta['vpp_setting']*(2*c/16383-1)/2,'.15g')])
    notes = f'''EDITOR LOCAL AFG1062 — AJUSTES PARA EL OPERADOR
Archivo a copiar al pendrive: ONDA.tfw
Puntos: {meta['points']}
Frecuencia de repetición de TODO el registro: {meta['repeat_hz']:.12g} Hz
Período: {meta['period_s']:.12g} s
Amplitud de escala completa: {meta['vpp_setting']:.12g} Vpp
Offset: {meta['offset_setting']:.12g} V
Carga seleccionada: {meta['load']}
Estos ajustes NO están guardados en el TFW. Configurarlos en el equipo.
La amplitud efectiva depende del rango usado por la señal y de la carga real.
N/T es la tasa equivalente de la tabla; no afirma el reloj DAC interno.
{meta['tfw_header']}
Compatibilidad física: validación exitosa en AFG1062, confirmada por el usuario.
No se comunica con el generador ni habilita salidas.
Extraer el ZIP y copiar ONDA.tfw al pendrive (no copiar solamente el ZIP).
En AFG1000: Arb > Others > File browse > USBDEVICE > Enter; seleccionar ONDA.tfw.
Seguir las opciones del firmware para cargar la onda en una memoria de usuario.
Comprobar forma, frecuencia, amplitud y offset antes de usarla en un ensayo.
'''
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('ONDA.tfw', tfw)
        z.writestr('DATOS.csv', stream.getvalue())
        z.writestr('AJUSTES.txt', notes)
        z.writestr('PROYECTO.json', json.dumps(spec, ensure_ascii=False, indent=2))
        z.writestr('METADATOS.json', json.dumps(meta, ensure_ascii=False, indent=2))
    return buf.getvalue()
