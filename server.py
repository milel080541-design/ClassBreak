"""로컬 실행: python3 server.py. 배포 시에는 api/handler.py가 진입점이다."""
import os,json,argparse
from pathlib import Path
from urllib.parse import urlparse,parse_qs,unquote
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
ROOT=Path(__file__).resolve().parent
# 로컬에서만 .env를 로드하며 값은 출력하지 않는다.
if not os.getenv('VERCEL') and (ROOT/'.env').exists():
    for line in (ROOT/'.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1);os.environ.setdefault(key.strip(),value.strip().strip("\"'"))
from backend import dispatch

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path.startswith('/api/'):
            status,data=dispatch(u.path,parse_qs(u.query));body=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if unquote(u.path) not in ['/','/index.html','/장소데이터.json']:
            self.send_error(404);return
        super().do_GET()
    def do_HEAD(self):
        if urlparse(self.path).path not in ['/','/index.html']:self.send_error(404);return
        super().do_HEAD()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);args=parser.parse_args()
    print(f'쉬는사이 http://localhost:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
