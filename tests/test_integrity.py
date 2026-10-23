import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assets import download_file, file_digest
from common import safe_name


PAYLOAD=b'fixed experiment asset\n'*128


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        offset=int(self.headers.get('Range','bytes=0-')[6:].split('-')[0])
        if self.path.startswith('/ignore'):
            self.send_response(200); data=PAYLOAD
        else:
            self.send_response(206 if offset else 200);data=PAYLOAD[offset:]
            if offset:self.send_header('Content-Range',f'bytes {offset}-{len(PAYLOAD)-1}/{len(PAYLOAD)}')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)


class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def entry(self):
        return {'size':len(PAYLOAD),'algorithm':'sha256','digest':hashlib.sha256(PAYLOAD).hexdigest()}
    def url(self,path):return f'http://127.0.0.1:{self.server.server_port}/{path}'
    def test_resume_correct_range(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'asset';p.with_name('asset.part').write_bytes(PAYLOAD[:73])
            download_file(self.url('range'),p,self.entry())
            self.assertEqual(p.read_bytes(),PAYLOAD);self.assertFalse(p.with_name('asset.part').exists())
    def test_server_ignoring_range_restarts_without_duplication(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'asset';p.with_name('asset.part').write_bytes(PAYLOAD[:73])
            download_file(self.url('ignore'),p,self.entry());self.assertEqual(p.read_bytes(),PAYLOAD)
    def test_bad_digest_is_never_published(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'asset';entry=self.entry();entry['digest']='0'*64
            with self.assertRaises(RuntimeError):download_file(self.url('range'),p,entry)
            self.assertFalse(p.exists())
    def test_corrupted_existing_asset_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'asset';p.write_bytes(b'bad')
            with self.assertRaises(RuntimeError):download_file(self.url('range'),p,self.entry())
            self.assertEqual(p.read_bytes(),b'bad')
    def test_git_blob_hash_includes_header(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'asset';p.write_bytes(PAYLOAD)
            self.assertEqual(file_digest(p,{'size':len(PAYLOAD),'algorithm':'git-sha1'}),hashlib.sha1(f'blob {len(PAYLOAD)}\0'.encode()+PAYLOAD).hexdigest())
    def test_run_names_cannot_escape_run_directory(self):
        for value in ['../old','/absolute','.','x/y','$(cmd)','a b']:
            with self.assertRaises(ValueError):safe_name(value)
        self.assertEqual(safe_name('smoke-001'),'smoke-001')


if __name__=='__main__':unittest.main()
