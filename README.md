# ClassBreak · 쉬는사이

성공회대학교 시간표를 등록하고, 수업 사이 공강에 다녀올 수 있는 주변 장소를 찾아보는 미니 웹서비스입니다. 대학 수업의 **Vibe Coding을 활용한 미니 웹서비스 개발 프로젝트**로 개발하고 있습니다.

## 주요 기능

- 요일·과목·수업 시간을 입력하고 브라우저에 시간표 저장
- 같은 날 수업을 시간순으로 정리해 공강 계산
- 식사·카페·공부·산책·놀거리·휴식별 주변 장소 표시
- 공강 길이와 이동·이용 시간을 고려한 추천
- 네이버 지도에서 위치 확인, 도보 경로와 이동 시간 조회
- 선택한 장소의 대중교통 시간 조회 및 도보와 비교

현재 개발 중인 버전입니다. 지도·외부 검색·길찾기를 사용하려면 인터넷 연결이 필요합니다.

## 실행 방법

서버는 Python 3 표준 라이브러리만 사용합니다. 별도 패키지 설치가 필요하지 않습니다.

```sh
git clone https://github.com/milel080541-design/ClassBreak.git
cd ClassBreak
cp .env.example .env
```

`.env`에 사용할 서비스의 인증 정보를 입력합니다. 키를 설정하지 않은 서비스는 사용할 수 없지만, 기본 장소 데이터와 공강·거리 기반 추천은 사용할 수 있습니다.

```dotenv
NAVER_SEARCH_CLIENT_ID=
NAVER_SEARCH_CLIENT_SECRET=
ODSAY_API_KEY=
# ODSAY_REFERER=http://localhost
```

- **지역 검색:** 네이버 클라우드 콘솔의 NAVER API HUB에서 발급한 Client ID·Client Secret을 사용합니다.
- **지도:** `index.html`의 `NAVER_MAP_CLIENT_ID`를 설정하고, Maps Application의 Web 서비스 URL에 실행 도메인을 등록합니다. 로컬 개발 주소는 `http://localhost`입니다. 지도용 ID는 브라우저에서 사용하며 검색 API 인증 정보와 다릅니다.
- **대중교통:** ODsay LAB의 인증키를 사용합니다. Web 키를 사용하면 등록한 URI와 `ODSAY_REFERER` 설정을 맞춥니다.
- **도보 길찾기:** 별도 키 없이 공개 도보 경로 서버를 사용합니다.

```sh
python3 server.py
```

브라우저에서 **http://localhost:8000**에 접속합니다. 포트를 바꾸려면 `python3 server.py --port 8001`로 실행합니다. 서버 코드나 `.env`를 바꾼 뒤에는 서버를 재시작해야 합니다.

`python3 -m http.server` 또는 Live Server는 API 프록시를 실행하지 않으므로 네이버 검색과 대중교통 조회를 사용할 수 없습니다. HTML을 `file://`로 직접 열면 현재 코드에서는 네이버 지도를 초기화하지 않습니다.

## 동작 구조

```text
브라우저 index.html
 ├─ 시간표 → localStorage
 ├─ 공강 계산·추천 → JavaScript
 ├─ 기본 장소 → HTML 안에 포함된 장소 41곳
 ├─ 지도 → NAVER Maps JavaScript SDK
 ├─ 도보 경로 → FOSSGIS OSRM 도보 서버
 └─ /api/places, /api/transit → server.py
      ├─ 네이버 지역 검색 → NAVER API HUB
      └─ 대중교통 검색 → ODsay → 로컬 JSON / 배포 Redis
```

비밀키는 서버가 `.env` 또는 환경변수에서 읽습니다. 실제 `.env`는 저장소에 포함하지 않으며, 서버에서도 웹 파일로 제공하지 않습니다.

네이버 검색을 사용할 수 없을 때는 HTML에 포함된 OpenStreetMap 장소 데이터를 사용합니다. `장소데이터.json`은 기본 데이터의 원본이며, 화면에서 이 JSON 파일을 별도로 불러오는 방식은 아닙니다.

## 추천 시간과 현재 한계

기본 계산 기준은 **왕복 이동 시간 + 활동 이용 시간 + 복귀 여유 10분 ≤ 공강**입니다.

- 도보 경로 조회 전에는 직선거리를 기반으로 시간을 추정합니다. 조회 후에는 경로 서버가 반환한 왕복 시간으로 해당 장소를 다시 계산합니다.
- 활동 이용 시간은 현재 고정 가정값입니다. 영업 여부, 혼잡도, 실제 체류 시간, 도서관 출입 조건은 보장하지 않습니다.
- 교내 장소는 보행 경로 연결 문제를 피하기 위해 거리 기반 추정치를 사용합니다.
- 대중교통은 버튼을 눌렀을 때만 조회합니다. **가는 편만 API로 확인하며, 오는 편 시간은 가는 편과 같다고 가정**합니다. 왕복 대기 여유 10분도 별도의 가정값입니다.
- 대중교통은 실시간 버스 도착 정보나 지도 위 도로 경로선을 제공하지 않습니다.
- 로컬에서 대중교통 조회에 성공하면 서버 폴더의 `transit_cache.json`에 저장합니다. 저장된 목적지는 서버 재시작 후에도 재사용하며, 파일이 없으면 첫 성공 조회 때 생성합니다.
- 조회한 경로와 네이버 검색 결과의 브라우저 메모리 캐시는 새로고침하면 사라집니다. 서버의 네이버 검색 캐시는 30분간 유지합니다.

네이버 영화관의 이용 시간 분류는 개선 과제로 남아 있습니다. 대중교통의 일시 오류나 저장소 잠금 경합은 재시도할 수 있도록 처리합니다. 동일 목적지의 동시 조회는 캐시 잠금 안에서 재확인해 중복 호출을 막습니다.

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| `index.html` | 화면, 스타일, 공강·추천 로직, 기본 장소 데이터, 지도 연동 |
| `server.py` | 로컬 웹서버 실행 |
| `backend.py` | 로컬과 Vercel이 공유하는 검색·대중교통 API 로직 |
| `cache_store.py` | 로컬 JSON 및 배포 Redis 저장, 중복 조회 방지 |
| `api/handler.py` | Vercel Python Function 진입점 |
| `build_static.py` | HTML과 기본 장소 JSON만 정적 배포 폴더로 복사 |
| `vercel.json` | 빌드, 함수 및 API 경로 설정 |
| `.env.example` | 인증 정보 설정 예시 |
| `장소데이터.json` | OpenStreetMap 기본 장소 데이터와 출처 |

배포 시 `server.py`를 실행할 수 있는 호스팅 환경과 서버 환경변수가 필요합니다. GitHub Pages만으로는 Python 서버가 실행되지 않습니다. 현재는 최종 과제의 단일 HTML 실행 조건을 별도로 검증·정리해야 하는 개발 단계입니다.

## Vercel 배포 설정

현재 저장소를 Vercel 프로젝트로 가져오고 Framework Preset은 **Other**로 선택합니다. 저장소 루트를 Root Directory로 사용하며, 빌드 명령과 출력 폴더는 `vercel.json` 설정을 따릅니다.

- 정적 화면: `build_static.py`가 `index.html`, `장소데이터.json`만 `public/`으로 복사합니다.
- 서버 API: `/api/config`, `/api/places`, `/api/transit` 요청을 `api/handler.py`가 처리합니다. 기존 화면의 API 주소를 바꿀 필요가 없습니다.
- 인증 정보: `.env`를 업로드하지 않고 Vercel 프로젝트의 Environment Variables에 기존 검색·ODsay 변수들을 등록합니다.
- 지도: 배포 도메인을 NAVER Maps의 Web 서비스 URL에 추가합니다.
- ODsay: 등록한 URI와 `ODSAY_REFERER`를 확인하고 배포 주소·인증 조건에 맞춥니다. Preview 도메인마다 인증이 되는지는 별도 확인이 필요합니다.

### 배포 환경의 경로 저장

Vercel에서는 프로젝트 폴더의 JSON을 수정하지 않습니다. Upstash Redis를 연결하고 다음 변수를 Vercel 환경변수로 등록합니다. Redis 데이터베이스를 직접 만들거나 Vercel Marketplace에서 연결한 후 **REST URL과 쓰기 가능한 REST Token**을 사용합니다.

```dotenv
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
```

경로는 Redis에 저장하고 다음 Function 실행에서도 재사용합니다. 같은 목적지의 중복 호출은 Redis 잠금으로 막으며, 여러 Function 인스턴스의 ODsay 요청도 공유 호출 간격을 둡니다. 경로 데이터에는 현재 자동 만료를 두지 않으므로 오래된 경로 갱신은 별도 관리가 필요합니다.

**Vercel에서 Redis가 없거나 연결이 실패하면 대중교통 API를 새로 호출하지 않습니다.** 저장되지 않은 요청을 반복해 ODsay 한도를 소비하는 것을 막기 위한 동작입니다. 지도·검색·도보 기능은 별도로 사용할 수 있습니다.

로컬에서는 기존 `python3 server.py` 명령과 `transit_cache.json` 저장을 유지합니다. 로컬에도 Upstash 변수를 설정하면 Redis를 사용합니다. 기존 로컬 JSON을 Redis에 자동 업로드하지는 않습니다.

저장소 코드, `.env`, 개발 문서와 로컬 경로 캐시는 정적 배포 대상에서 제외합니다. 환경변수 변경 후에는 새 배포가 필요합니다. 이 구조는 배포 준비 코드이며 실제 Vercel·Redis 인증은 배포 후 확인해야 합니다.

## 데이터 출처

기본 장소 데이터는 2026년 11월 2일 수집한 성공회대학교 주변 OpenStreetMap 데이터입니다.

- [OpenStreetMap contributors · ODbL](https://www.openstreetmap.org/copyright)
- [NAVER Maps JavaScript API](https://navermaps.github.io/maps.js.ncp/docs/)
- [NAVER API HUB 지역 검색 API](https://api.ncloud-docs.com/docs/naver-api-hub-search-local)
- [FOSSGIS OSRM 경로 서버](https://routing.openstreetmap.de/about.html)
- [ODsay LAB API](https://lab.odsay.com/guide/releaseReference?platform=web)
