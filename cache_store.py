"""대중교통 캐시: 로컬 JSON / Vercel Upstash Redis REST."""
import os,json,time,uuid,threading,tempfile
from pathlib import Path
from contextlib import contextmanager
from urllib.request import Request,urlopen

class CacheUnavailable(Exception):pass
class CacheBusy(Exception):pass

class LocalStore:
    remote=False
    def __init__(self,path):self.path=Path(path);self.lock=threading.RLock()
    def read(self):
        if not self.path.exists():return {}
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError()
            return data
        except (OSError,ValueError) as e:raise CacheUnavailable() from e
    def get(self,key):
        with self.lock:return self.read().get(key)
    def set(self,key,value):
        with self.lock:
            data=self.read();data[key]=value
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.path.parent,delete=False) as f:
                    tmp=Path(f.name);json.dump(data,f,ensure_ascii=False)
                os.replace(tmp,self.path)
            except OSError as e:
                if 'tmp' in locals():tmp.unlink(missing_ok=True)
                raise CacheUnavailable() from e
    @contextmanager
    def claim(self,key):
        # 로컬 단일 서버에서는 조회·저장을 함께 직렬화한다.
        with self.lock:yield

class UnavailableStore:
    remote=True
    def get(self,key):raise CacheUnavailable()
    def set(self,key,value):raise CacheUnavailable()

class RedisStore:
    remote=True
    prefix='classbreak:v1:37.48752,126.825799:'
    def __init__(self,url,token):self.url=url.rstrip('/');self.token=token
    def command(self,*args):
        try:
            req=Request(self.url,data=json.dumps(list(args)).encode(),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method='POST')
            with urlopen(req,timeout=4) as r:data=json.load(r)
            if 'error' in data:raise ValueError()
            return data['result']
        except Exception as e:raise CacheUnavailable() from e
    def get(self,key):
        value=self.command('GET',self.prefix+'transit:'+key)
        if value is None:return None
        try:
            data=json.loads(value)
            if not isinstance(data,dict):raise ValueError()
            return data
        except (ValueError,TypeError) as e:raise CacheUnavailable() from e
    def set(self,key,value):
        if self.command('SET',self.prefix+'transit:'+key,json.dumps(value,ensure_ascii=False))!='OK':raise CacheUnavailable()
    @contextmanager
    def claim(self,key):
        lock_key=self.prefix+'lock:'+key;token=uuid.uuid4().hex
        if self.command('SET',lock_key,token,'NX','EX',90)!='OK':raise CacheBusy()
        try:yield
        finally:
            # 다른 실행의 잠금을 지우지 않도록 토큰이 일치할 때만 해제한다.
            try:self.command('EVAL',"if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,lock_key,token)
            except CacheUnavailable:pass  # 잠금은 만료된다. 이미 저장된 성공 결과는 반환한다.
    def throttle(self):
        # Function 인스턴스 사이에서도 API 연속 호출을 제한한다.
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if self.command('SET',self.prefix+'odsay-rate','1','NX','PX',1100)=='OK':return
            time.sleep(0.3)
        raise CacheBusy()

def make_store():
    url=os.getenv('UPSTASH_REDIS_REST_URL','');token=os.getenv('UPSTASH_REDIS_REST_TOKEN','')
    if url.startswith('https://') and token:return RedisStore(url,token)
    # 읽기 전용 배포 영역에 로컬 JSON을 쓰는 대체 동작을 하지 않는다.
    if os.getenv('VERCEL'):return UnavailableStore()
    return LocalStore(Path(__file__).resolve().parent/'transit_cache.json')
