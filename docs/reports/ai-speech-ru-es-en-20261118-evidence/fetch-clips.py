"""Fetch complete public CC0 clips from pinned uncompressed sorted tar using bounded HTTP ranges."""
import urllib.request,json,hashlib,time,concurrent.futures
from pathlib import Path
ROOT=Path(__file__).parent; REV='8262c16bf297c87a9cd88c51997c4758ed7a8ba2'
SELECT={'en':['common_voice_en_18338596.mp3','common_voice_en_5478736.mp3','common_voice_en_18274308.mp3'],'es':['common_voice_es_18395868.mp3','common_voice_es_20884798.mp3','common_voice_es_19958818.mp3'],'ru':['common_voice_ru_37452149.mp3','common_voice_ru_27710882.mp3','common_voice_ru_18856190.mp3']}
SIZES={'en':711150592,'es':749712896,'ru':396584448}
def fetch(url,start,end):
 req=urllib.request.Request(url+'?range_start='+str(start),headers={'Range':f'bytes={start}-{end}'})
 with urllib.request.urlopen(req,timeout=30) as r:
  assert r.status==206 and r.headers['Content-Range'].startswith(f'bytes {start}-'),'RANGE_NOT_HONORED'
  data=r.read(end-start+2);assert len(data)==end-start+1
  return data

def headers(data,start):
 for off in range(0,len(data)-511,512):
  b=data[off:off+512]
  if b[257:262]!=b'ustar':continue
  try:
   check=int(b[148:156].strip(b'\0 '),8)
   if sum(b[:148])+sum(b[156:])+256!=check:continue
   name=b[:100].split(b'\0')[0].decode();size=int(b[124:136].strip(b'\0 '),8)
  except (ValueError,UnicodeError):continue
  if name.endswith('.mp3'):yield name.rsplit('/',1)[-1],size,start+off+512

def one(lang,name):
 out=ROOT/name
 url=f'https://huggingface.co/datasets/fsicoli/common_voice_17_0/resolve/{REV}/audio/{lang}/test/{lang}_test_0.tar'
 if out.exists():return {'file':name,'source_audio_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
 low,high=0,SIZES[lang]; requests=0;downloaded=0
 for attempt in range(30):
  middle=((low+high)//2)//512*512; end=min(middle+524288-1,SIZES[lang]-1)
  data=fetch(url,middle,end);requests+=1;downloaded+=len(data); entries=list(headers(data,middle))
  assert entries,'NO_HEADER_IN_WINDOW'
  for found,size,pos in entries:
   if found==name:
    audio=fetch(url,pos,pos+size-1);out.write_bytes(audio)
    return {'file':name,'source_audio_sha256':hashlib.sha256(audio).hexdigest(),'tar_offset':pos,'tar_bytes':size,'requests':requests+1,'downloaded_bytes':downloaded+size,'source_url':url}
  if entries[0][0]>name:high=middle
  elif entries[-1][0]<name:low=entries[-1][2]+((entries[-1][1]+511)//512)*512
  else:raise ValueError('MISSING_SORTED_ENTRY')
  assert low<high,'CLIP_NOT_FOUND'
 raise ValueError('SEARCH_LIMIT')

def language(lang):
 candidates=json.loads((ROOT/f'{lang}-candidates.json').read_text(encoding='utf8'));results=[]
 for name in SELECT[lang]:
  r=one(lang,name);r.update(next(c for c in candidates if c['path']==name));r.update(language=lang,reference=r.pop('sentence'),kind='public-human-common-voice-17',expected='reject_unsupported_narrative')
  results.append(r);print(lang,name,'fetched',flush=True)
 return results
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3)as ex:rows=sum(list(ex.map(language,SELECT)),[])
 (ROOT/'public-manifest.json').write_text(json.dumps({'dataset':'fsicoli/common_voice_17_0','revision':REV,'license':'CC0-1.0','samples':rows},ensure_ascii=False,indent=2),encoding='utf8')
