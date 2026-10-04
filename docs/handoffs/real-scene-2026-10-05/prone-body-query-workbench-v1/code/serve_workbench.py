"""Local-only review persistence. No fitting, no external upload, no source mutation."""
import argparse,json
from datetime import datetime,timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path


class ReviewHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path!='/api/reviews':self.send_error(404);return
        review=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        path=self.server.review_dir/('review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        path.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        response=json.dumps(dict(saved_file=str(path.resolve()))).encode()
        self.send_response(201);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(response)));self.end_headers();self.wfile.write(response)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,required=True);p.add_argument('--reviews',type=Path,required=True);p.add_argument('--port',type=int,default=8865);args=p.parse_args()
    args.reviews.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(ReviewHandler,directory=str(args.site.resolve())));server.review_dir=args.reviews.resolve()
    print('Local review workbench http://127.0.0.1:'+str(args.port)+'/workbench.html',flush=True);server.serve_forever()
