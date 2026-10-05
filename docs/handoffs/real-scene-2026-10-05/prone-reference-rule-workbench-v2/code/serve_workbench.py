"""Reference completion service using the existing cached patient assets."""
import argparse
import json
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from reference_completion import propose
from rule_pipeline import generate


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/CASE_INDEX.json' or self.path.startswith('/cases/'):
            path = self.server.assets/self.path.lstrip('/')
            payload = path.read_bytes()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)
        else:
            super().do_GET()

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path in ['/api/rules', '/api/propose']:
            mesh = json.loads((self.server.assets/'cases'/(request['subject']+'.json')).read_text())
            assert mesh['mesh_sha256'] == request['mesh_sha256']
            if self.path == '/api/propose': output = propose(mesh, request['references'])
            else: output = generate(mesh, request['references'], request['b_cun_mm'], request['scale_source'])
            code = 200
        elif self.path == '/api/reviews':
            dest = self.server.reviews/('review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
            dest.write_text(json.dumps(request, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
            output = dict(saved_file=str(dest.resolve())); code = 201
        else: self.send_error(404); return
        payload = json.dumps(output).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--site', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True); p.add_argument('--reviews', type=Path, required=True)
    p.add_argument('--port', type=int, default=8867); args = p.parse_args(); args.reviews.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(args.site.resolve())))
    server.assets = args.assets.resolve(); server.reviews = args.reviews.resolve()
    print('Two-reference workbench http://127.0.0.1:'+str(args.port)+'/index.html', flush=True)
    server.serve_forever()
