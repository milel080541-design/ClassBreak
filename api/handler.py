"""Vercel Python Function. .env 및 로컬 서버를 로드하지 않는다."""
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from backend import dispatch

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u=urlparse(self.path);args=parse_qs(u.query)
        endpoint=args.pop('endpoint',[''])[0]
        path='/api/'+endpoint if endpoint else u.path
        status,data=dispatch(path,args)
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
