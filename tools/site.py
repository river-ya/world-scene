"""Dependency-free validation, static build, subpath preview, and scoped cleanup."""
import argparse, hashlib, http.server, json, pathlib, re, shutil, urllib.parse
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
BASE = '/world-scene/'

def read(name): return json.loads((SRC / 'data' / f'{name}.json').read_text())
def validate():
    site, cases = read('site'), read('cases')
    assert site['basePath'] == BASE, 'The deployment base path is fixed.'
    ids=set(); videos=set(); video_hashes=set(); ready_count=0
    def resource(value, required=False):
        if not value:
            assert not required, 'Missing required media'
            return
        if value.startswith('https://'): return
        assert not urllib.parse.urlparse(value).scheme and not value.startswith('/'), f'Use relative paths or HTTPS: {value}'
        path=(SRC/value).resolve()
        assert path.is_relative_to(SRC.resolve()) and path.is_file(), f'Missing local resource: {value}'
    for c in cases:
        assert c.get('section') in ['flashworld','luciddreamer','comparison','angles'], 'Every case needs a valid section'
        for key in ['id','sourceImageId','title','category','inputImage','prompt','results']: assert key in c, f'Missing {key}'
        assert c['id'] not in ids, 'Duplicate case ID';ids.add(c['id'])
        assert c['results'], 'Every case needs at least one result with an explicit status'
        for r in c['results']:
            for key in ['method','version','trajectory','video','poster','resolution','status','notes','comparisonGroup','protocolAligned']: assert key in r, f'Missing result {key}'
            assert r['status'] in ['ready','pending','unavailable'], 'Invalid status'
            if r['status'] != 'ready': continue
            ready_count+=1
            resource(c['inputImage'],True)
            assert isinstance(c['prompt'],str) and c['prompt'].strip(), 'Ready requires the actual prompt'
            resource(r['video'],True);resource(r['poster'],True)
            assert r['video'] not in videos, 'The same video must not be counted as a separate result';videos.add(r['video'])
            if not r['video'].startswith('https://'):
                digest=hashlib.sha256((SRC/r['video']).read_bytes()).hexdigest()
                assert digest not in video_hashes, 'Identical video copies must not be counted as separate results'
                video_hashes.add(digest)
            assert len(r['resolution'])==2 and all(isinstance(x,int) and x>0 for x in r['resolution'])
            assert r.get('fps',0)>0 and r.get('duration',0)>0, 'Record real FPS and duration'
            if r['protocolAligned']:
                assert r['comparisonGroup'], 'Aligned results require comparisonGroup'
                assert all(r.get('protocol',{}).get(k) for k in ['cameraPathHash','intrinsicsHash','sampleTimesHash','coordinateSystem','inputImageHash','promptHash']), 'Aligned results require protocol evidence'
    for r in site['copy']['resources']: resource(r['url'])
    e=site.get('evaluation')
    if e:
        assert all(e.get(k) for k in ['dataset','sampleCount','protocol','source','metrics','rows']), 'Incomplete evaluation evidence'
        assert isinstance(e['sampleCount'],int) and e['sampleCount']>0
        resource(e['source'])
        for m in e['metrics']: assert m['direction'] in ['higher','lower']
        for row in e['rows']:
            for m in e['metrics']: assert isinstance(row['values'][m['id']],(int,float)), 'Metrics must be numeric'
    total=0;largest=(0,'')
    for f in SRC.rglob('*'):
        if not f.is_file(): continue
        assert not f.is_symlink(), 'Do not publish symlinks'
        size=f.stat().st_size;total+=size;largest=max(largest,(size,str(f.relative_to(SRC))))
        assert size<100*1024**2, f'File exceeds GitHub individual file limit: {f}'
        if f.suffix in ['.html','.css','.js','.json']:
            text=f.read_text()
            assert not re.search(r'(?:file://|/mnt/[a-z]/|/home/|/data-nfs/)',text), f'Local filesystem reference in {f}'
    assert total<1024**3, 'Published site must stay below 1 GiB'
    print(f'VALID: {len(cases)} cases, {ready_count} ready results; source {total/1024**2:.2f} MiB; largest {largest[0]/1024**2:.2f} MiB ({largest[1]})')

def clean():
    dist=ROOT/'dist'
    assert dist.parent==ROOT and dist.name=='dist' and not dist.is_symlink()
    if dist.exists(): shutil.rmtree(dist)
    for directory in [ROOT/'tools/__pycache__',ROOT/'tests/__pycache__']:
        if directory.exists() and not directory.is_symlink(): shutil.rmtree(directory)
    print('Removed website dist and website Python caches only.')

def build():
    validate();clean();shutil.copytree(SRC,ROOT/'dist');(ROOT/'dist/.nojekyll').touch()
    print(f'Static output: {ROOT / "dist"}')

class Preview(http.server.SimpleHTTPRequestHandler):
    def translate_path(self,path):
        url=urllib.parse.urlparse(path).path
        if not url.startswith(BASE): return str(ROOT/'__not_served__')
        stripped=urllib.parse.unquote(url[len(BASE):])
        resolved=(ROOT/'dist'/stripped).resolve()
        if not resolved.is_relative_to((ROOT/'dist').resolve()): return str(ROOT/'__not_served__')
        return str(resolved)
    def do_GET(self):
        if self.path=='/': self.send_response(302);self.send_header('Location',BASE);self.end_headers();return
        if self.path==BASE.rstrip('/'): self.send_response(301);self.send_header('Location',BASE);self.end_headers();return
        path=pathlib.Path(self.translate_path(self.path))
        if self.headers.get('Range') and path.is_file():
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',self.headers['Range'])
            if match:
                size=path.stat().st_size;start=int(match[1]);end=min(int(match[2]) if match[2] else size-1,size-1)
                if start>=size or start>end: self.send_error(416);return
                self.send_response(206);self.send_header('Content-Type',self.guess_type(str(path)));self.send_header('Content-Range',f'bytes {start}-{end}/{size}');self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.end_headers()
                try:
                    with path.open('rb') as f:
                        f.seek(start);remaining=end-start+1
                        while remaining:
                            chunk=f.read(min(65536,remaining))
                            if not chunk: break
                            self.wfile.write(chunk);remaining-=len(chunk)
                except (BrokenPipeError,ConnectionResetError): pass
                return
        try: super().do_GET()
        except (BrokenPipeError,ConnectionResetError): pass
    def log_message(self,fmt,*args):
        if args and str(args[1]) not in ['200','206','304']: super().log_message(fmt,*args)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['check','build','preview','clean']);p.add_argument('--port',type=int,default=8000);args=p.parse_args()
    if args.command=='check': validate()
    elif args.command=='clean': clean()
    elif args.command=='build': build()
    else:
        if not (ROOT/'dist/index.html').exists(): build()
        print(f'Local preview: http://127.0.0.1:{args.port}{BASE}',flush=True)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),Preview)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
if __name__=='__main__': main()
