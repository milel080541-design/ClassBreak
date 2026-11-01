"""실행: python3 server.py (비밀키는 이 폴더의 .env 또는 서버 환경변수)."""
import os,json,re,html,math,time,threading,argparse
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.request import Request,urlopen
from urllib.parse import urlparse,parse_qs,urlencode,quote
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parent
for line in (ROOT/'.env').read_text().splitlines() if (ROOT/'.env').exists() else []:
    if line.strip() and not line.lstrip().startswith('#') and '=' in line:
        key,value=line.split('=',1);os.environ.setdefault(key.strip(),value.strip().strip('\"\''))
CLIENT=os.getenv('NAVER_SEARCH_CLIENT_ID','');SECRET=os.getenv('NAVER_SEARCH_CLIENT_SECRET','')
TRANSIT_KEY=os.getenv('ODSAY_API_KEY','')
# ODsay Web 키는 등록한 URI와 Referer가 정확히 같아야 인증된다(포트·경로 포함 시 실패). Server 키(IP 등록)면 무시된다.
ODSAY_REFERER=os.getenv('ODSAY_REFERER','http://localhost')
CACHE={};LOCK=threading.Lock()
# ODsay 결과는 파일에 저장해 서버를 재시작해도 다시 호출하지 않는다(호출 한도가 작음).
TRANSIT_CACHE_FILE=ROOT/'transit_cache.json'
try:TRANSIT_CACHE=json.loads(TRANSIT_CACHE_FILE.read_text(encoding='utf-8'))
except (OSError,ValueError):TRANSIT_CACHE={}
CAMPUS=(37.48752,126.825799)
CAMPUS_ADDRESS='연동로 320'  # 성공회대학교 도로명 주소. 이 주소의 가게는 교내 건물 안에 있다.
TERMS={'식사':'음식점','카페':'카페','공부':'도서관','산책':'공원','휴식':'공원','놀거리':'문화시설'}
# 지역 검색은 요청당 최대 5개라 학교 주변 동네·역 이름으로 나눠 검색한다. 1.8km 밖 결과는 normalize에서 버린다.
QUERIES={
    '식사':['성공회대 맛집','항동 맛집','천왕역 맛집','온수역 맛집','오류동 맛집'],
    '카페':['성공회대 카페','항동 카페','천왕역 카페','온수역 카페','오류동 카페'],
    '공부':['성공회대 스터디카페','항동 도서관','천왕역 스터디카페','온수역 스터디카페'],
    '산책':['항동 공원','푸른수목원','온수 공원','천왕 공원'],
    '휴식':['항동 공원','푸른수목원','온수 공원','천왕 공원'],
    '놀거리':['천왕역 노래방','온수역 노래방','온수역 PC방','천왕역 PC방','온수역 볼링장'],
}
# 대중교통 키가 있으면 반경을 4km로 넓히고 역 주변 상권을 추가로 검색한다. 키가 없으면 걸어서 갈 수 있는 1.8km만.
FAR_AREAS=['역곡역','개봉역','광명사거리역','고척동']
FAR_KEYWORDS={'식사':['맛집'],'카페':['카페'],'공부':['스터디카페','도서관'],'산책':['공원'],'휴식':['공원'],'놀거리':['영화관','노래방','볼링장']}
SEARCH_RADIUS=4000 if TRANSIT_KEY else 1800
if TRANSIT_KEY:
    for _activity,_words in FAR_KEYWORDS.items():QUERIES[_activity]=QUERIES[_activity]+[f'{a} {w}' for a in FAR_AREAS for w in _words]
# 네이버 category 문자열(예: '음식점>한식', '카페,디저트>카페')로 활동을 다시 분류한다. 위에서부터 먼저 맞는 규칙을 쓴다.
RULES=[
    (('술집','주점','호프','포차','바(BAR)'),None),  # 공강 식사 후보에서 제외
    (('스터디카페','독서실','도서관','북카페'),['공부']),
    (('카페','디저트','베이커리','커피'),['카페']),
    (('공원','수목원','산책','둘레길','정원'),['산책','휴식']),
    (('노래방','PC방','볼링','보드게임','영화관','오락실','방탈출','당구','만화방'),['놀거리']),
    (('음식점','한식','중식','일식','양식','분식','치킨','패스트푸드','햄버거','피자','국밥','고기','육류','찌개','국수','돈가스','샐러드','도시락','뷔페','아시아음식'),['식사']),
]
def classify(category,activity):
    for words,types in RULES:
        if any(w in category for w in words):return types
    return [activity]  # 분류 불가면 검색한 활동으로 둔다
def distance_meters(lat,lng):
    rad=math.radians;dlat=rad(lat-CAMPUS[0]);dlng=rad(lng-CAMPUS[1])
    h=math.sin(dlat/2)**2+math.cos(rad(CAMPUS[0]))*math.cos(rad(lat))*math.sin(dlng/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,h)))
def normalize(items,activity):
    results=[]
    for item in items:
        try:
            lat=float(item['mapy']);lng=float(item['mapx'])
            if abs(lat)>90:lat/=10000000
            if abs(lng)>180:lng/=10000000
            if not (-90<=lat<=90 and -180<=lng<=180 and distance_meters(lat,lng)<=SEARCH_RADIUS):continue
            name=html.unescape(re.sub('<[^>]*>','',item['title'])).strip()
            if not name:continue
            category=html.unescape(item.get('category',''))
            types=classify(category,activity)
            if not types:continue
            address=item.get('roadAddress') or item.get('address') or ''
            # 상세주소(층·호)까지 넣으면 네이버 지도 검색 결과가 없어서 상호 + 시군구(예: 구로구)로 검색한다.
            parts=address.split();district=parts[1] if len(parts)>1 else ''
            results.append({'id':f'naver/{lng:.6f}/{lat:.6f}/{name}','name':name,'lat':lat,'lng':lng,'types':types,'kind':category.split('>')[-1] or TERMS[activity],'amenity':'naver','openingHours':None,'source':'https://map.naver.com/p/search/'+quote(f'{name} {district}'.strip()),'address':address or None,'provider':'naver','onCampus':CAMPUS_ADDRESS in address})
        except (KeyError,ValueError,TypeError):continue
    return results
def dedupe(places):
    seen=[]
    for p in places:
        key=re.sub(r'\s','',p['name'])
        old=next((s for s in seen if re.sub(r'\s','',s['name'])==key and distance_between(s,p)<100),None)
        if old:old['types']=sorted(set(old['types'])|set(p['types']))
        else:seen.append(p)
    return seen
def distance_between(a,b):
    return math.hypot((a['lat']-b['lat'])*111195,(a['lng']-b['lng'])*88200)
def naver_local(query):
    # NAVER API HUB(네이버 클라우드 콘솔에서 발급). 파라미터·응답은 구 개발자센터 지역 검색과 같고 주소·헤더만 다르다.
    url='https://naverapihub.apigw.ntruss.com/search/v1/local?'+urlencode({'query':query,'display':5,'sort':'random'})
    req=Request(url,headers={'X-NCP-APIGW-API-KEY-ID':CLIENT,'X-NCP-APIGW-API-KEY':SECRET,'User-Agent':'ClassBreak/0.1'})
    with urlopen(req,timeout=12) as r:return json.load(r).get('items',[])
def search_places(activity):
    errors=[];places=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for query,future in [(q,pool.submit(naver_local,q)) for q in QUERIES[activity]]:
            try:places+=normalize(future.result(),activity)
            except HTTPError as e:errors.append(e.code)
            except Exception:errors.append(None)
    if errors and len(errors)==len(QUERIES[activity]):
        if 401 in errors:raise PermissionError()
        raise ConnectionError(errors[0])
    return dedupe(places)
# ODsay는 초당 호출 수를 넘으면 429(Too Many Requests)를 준다. 서버 전체에서 한 번에 하나씩, 0.4초 간격으로 보내고 429면 잠시 후 재시도한다.
ODSAY_LOCK=threading.Lock();ODSAY_LAST=[0.0]
def odsay_error(data):
    err=data.get('error')
    if not err:return None
    err=err[0] if isinstance(err,list) and err else err
    if not isinstance(err,dict):return ('',str(err))
    return (str(err.get('code','')),err.get('msg') or err.get('message') or '')
def odsay_get(url):
    for attempt in range(3):
        with ODSAY_LOCK:
            wait=ODSAY_LAST[0]+0.4-time.time()
            if wait>0:time.sleep(wait)
            try:
                with urlopen(Request(url,headers={'User-Agent':'ClassBreak/0.1','Referer':ODSAY_REFERER}),timeout=12) as r:data=json.load(r)
            except HTTPError as e:
                if e.code!=429:raise
                data={'error':{'code':'429','msg':'Too Many Requests'}}
            finally:ODSAY_LAST[0]=time.time()
        err=odsay_error(data)
        if err and (err[0]=='429' or 'Too Many' in err[1]):time.sleep(1.5*(attempt+1));continue
        return data
    return data
def transit_path(start,end):
    query={'apiKey':TRANSIT_KEY,'SX':start[0],'SY':start[1],'EX':end[0],'EY':end[1],'OPT':0,'SearchType':0,'SearchPathType':0}
    data=odsay_get('https://api.odsay.com/v1/api/searchPubTransPathT?'+urlencode(query))
    # ODsay는 오류도 HTTP 200으로 보내고 error에 담는다(객체 또는 배열). 인증·한도 오류를 '경로 없음'으로 오해하지 않도록 구분한다.
    err=odsay_error(data)
    if err:
        code,msg=err
        if code in ('-98','-99','3','4','5','6'):raise ValueError('이 구간의 대중교통 경로를 찾지 못했습니다.')
        raise RuntimeError(f'ODsay 오류({code}) {msg}'.strip())
    paths=data.get('result',{}).get('path',[])
    paths=[p for p in paths if p.get('pathType') in [1,2,3] and isinstance(p.get('info',{}).get('totalTime'),(float,int)) and p['info']['totalTime']>0]
    if not paths:raise ValueError('이 구간의 대중교통 경로를 찾지 못했습니다.')
    path=min(paths,key=lambda p:p['info']['totalTime']);segments=[]
    for sub in path.get('subPath',[]):
        kind=sub.get('trafficType');lanes=sub.get('lane',[])
        label='도보' if kind==3 else ('버스 '+str(lanes[0].get('busNo','')) if kind==2 and lanes else lanes[0].get('name','지하철') if kind==1 and lanes else '대중교통')
        segments.append({'label':label,'minutes':sub.get('sectionTime',0),'from':sub.get('startName',''),'to':sub.get('endName','')})
    return {'minutes':math.ceil(path['info']['totalTime']),'segments':segments}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
    def json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/api/config':return self.json(200,{'naverSearch':bool(CLIENT and SECRET),'transit':bool(TRANSIT_KEY),'radius':SEARCH_RADIUS})
        if u.path=='/api/transit':
            if not TRANSIT_KEY:return self.json(503,{'error':'대중교통 API 키 설정 후 서버를 다시 실행하세요.'})
            try:
                args=parse_qs(u.query);lng=float(args.get('lng',[''])[0]);lat=float(args.get('lat',[''])[0])
                if distance_meters(lat,lng)>SEARCH_RADIUS+300:raise ValueError()
            except (ValueError,TypeError):return self.json(400,{'error':'학교 주변 목적지만 조회할 수 있습니다.'})
            key=f'{lng:.6f},{lat:.6f}'
            with LOCK:cached=TRANSIT_CACHE.get(key)
            if cached:return self.json(200,cached)
            try:
                # 호출 한도를 아끼려고 가는 편만 조회하고, 오는 편은 같은 경로·시간으로 가정한다.
                go=transit_path((126.825799,37.48752),(lng,lat))
            except ValueError as e:return self.json(404,{'error':str(e)})
            except RuntimeError as e:return self.json(502,{'error':str(e)+' · ODsay 키 설정과 호출 한도를 확인하세요.'})
            except Exception:return self.json(502,{'error':'대중교통 경로 조회 실패. 잠시 후 다시 시도하세요.'})
            back={'minutes':go['minutes'],'segments':[{**s,'from':s['to'],'to':s['from']} for s in reversed(go['segments'])],'assumed':True}
            result={'outbound':go,'inbound':back,'minutes':go['minutes']*2,'waitBuffer':10}
            with LOCK:
                TRANSIT_CACHE[key]=result
                TRANSIT_CACHE_FILE.write_text(json.dumps(TRANSIT_CACHE,ensure_ascii=False),encoding='utf-8')
            return self.json(200,result)
        if u.path=='/api/places':
            activity=parse_qs(u.query).get('activity',[''])[0]
            if activity not in TERMS:return self.json(400,{'error':'활동을 확인하세요.'})
            if not CLIENT or not SECRET:return self.json(503,{'error':'네이버 검색 API 키 설정 후 서버를 다시 실행하세요.'})
            with LOCK:
                cached=CACHE.get(activity)
            if cached and time.time()-cached[0]<1800:return self.json(200,{'places':cached[1]})
            try:places=search_places(activity)
            except PermissionError:return self.json(502,{'error':'네이버 검색 인증 실패(401). NAVER API HUB Application의 Client ID/Secret과 검색 API 이용 신청 상태를 확인하세요.'})
            except ConnectionError as e:return self.json(502,{'error':f'네이버 검색 응답 오류({e.args[0]}). 잠시 후 다시 시도하세요.'})
            with LOCK:CACHE[activity]=(time.time(),places)
            return self.json(200,{'places':places})
        # 비밀키·코드·디렉터리 목록은 웹으로 제공하지 않는다.
        if u.path not in ['/','/index.html','/장소데이터.json'] and u.path!='/'+__import__('urllib.parse',fromlist=['quote']).quote('장소데이터.json'):
            self.send_error(404);return
        super().do_GET()
    def do_HEAD(self):
        if urlparse(self.path).path not in ['/','/index.html']:self.send_error(404);return
        super().do_HEAD()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);args=parser.parse_args()
    print(f'쉬는사이 http://localhost:{args.port} | 네이버 검색: '+('연결 설정됨' if CLIENT and SECRET else '.env 설정 대기'),flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
