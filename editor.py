"""Local browser UI; no dependencies, drivers or administrator required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import base64
import json
import secrets
import threading
import webbrowser
from waveform import build, package, parse_tfw

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(24)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def send(self, data, mime='application/json', status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def local(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.local(): return self.send(b'Forbidden', 'text/plain', 403)
        if self.path == '/':
            return self.send((ROOT/'interface.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN).encode(), 'text/html; charset=utf-8')
        self.send(b'Not found', 'text/plain', 404)

    def do_POST(self):
        if not self.local() or self.headers.get('X-Editor-Token') != TOKEN:
            return self.send(b'Forbidden', 'text/plain', 403)
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 12*1024*1024: raise ValueError('Solicitud vacía o mayor que 12 MB.')
            data = json.loads(self.rfile.read(size))
            if self.path == '/close':
                self.send(b'{}')
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if self.path == '/template':
                codes = parse_tfw(base64.b64decode(data['template'], validate=True))
                return self.send(json.dumps({'points': len(codes)}).encode())
            if self.path == '/preview':
                y, codes, meta = build(data)
                # Preserve extrema inside each display bucket, so short pulses remain visible.
                n, indexes = len(y), set([0, len(y)-1])
                step = max(1, (n+1499)//1500)
                for start in range(0,n,step):
                    end = min(start+step,n)
                    indexes.add(min(range(start,end), key=y.__getitem__))
                    indexes.add(max(range(start,end), key=y.__getitem__))
                points = [[i*meta['sample_interval_s'], meta['offset_setting']+meta['vpp_setting']*(2*codes[i]/16383-1)/2] for i in sorted(indexes)]
                return self.send(json.dumps({'meta':meta, 'plot':points}, allow_nan=False).encode())
            if self.path == '/export':
                template = base64.b64decode(data['template'], validate=True) if data.get('template') else None
                return self.send(package(data['spec'], template), 'application/zip')
            self.send(b'Not found', 'text/plain', 404)
        except (ValueError, TypeError, KeyError, SyntaxError, ArithmeticError, RecursionError) as exc:
            self.send(json.dumps({'error': str(exc)}, ensure_ascii=False).encode(), status=400)


def main():
    parser = argparse.ArgumentParser(description='Editor local de ondas AFG1062')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        url = f'http://127.0.0.1:{server.server_port}/'
        print(url, flush=True)
        if not args.no_browser: webbrowser.open(url)
        try: server.serve_forever()
        except KeyboardInterrupt: pass


if __name__ == '__main__': main()
