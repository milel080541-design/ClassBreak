"""배포 정적 파일은 명시한 두 파일만 복사한다. .env나 소스는 복사하지 않는다."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
out=ROOT/'public'
if out.exists():shutil.rmtree(out)
out.mkdir()
for name in ['index.html','장소데이터.json']:shutil.copyfile(ROOT/name,out/name)
