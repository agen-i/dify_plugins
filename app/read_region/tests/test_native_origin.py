import subprocess
import sys
from pathlib import Path


def test_authenticated_rpc_origin_not_file_or_environment_and_no_upload():
    app = Path(__file__).resolve().parents[1]
    code = r"""
import os
from types import SimpleNamespace
from vision_core.origin import native_origin_from_session
from vision_core.fetch import preview_path
from vision_core.images import ImageFailure
from dify_plugin.core.entities.invocation import InvokeType
calls=[];closed=[]
class NativeFile:
 def upload(self,*args):raise AssertionError('actual upload forbidden')
 def _backwards_invoke(self,kind,dtype,payload):
  assert kind is InvokeType.UploadFile and dtype is dict
  assert payload=={'filename':'read_region_native_origin.png','mimetype':'image/png'}
  calls.append(payload)
  try:yield {'url':'http://authoritative.example.invalid:5001/files/upload?token=rpc-secret-canary'}
  finally:closed.append(True)
os.environ['DIFY_INNER_API_URL']='http://model-chosen.example.invalid'
origin=native_origin_from_session(SimpleNamespace(file=NativeFile()))
assert (origin.scheme,origin.host,origin.port)==('http','authoritative.example.invalid',5001)
assert len(calls)==len(closed)==1 and 'rpc-secret-canary' not in repr(origin)
try:preview_path('http://model-chosen.example.invalid/files/arbitrary',origin);raise AssertionError('model origin accepted')
except ImageFailure:pass
class BadFile:
 def _backwards_invoke(self,*args):
  raise RuntimeError('rpc-secret-canary private URL')
try:native_origin_from_session(SimpleNamespace(file=BadFile()));raise AssertionError('failure accepted')
except ImageFailure as e:assert str(e)=='NATIVE_ORIGIN_UNAVAILABLE'
class Oversized:
 def _backwards_invoke(self,*args):yield {'url':'http://native.invalid/','extra':'x'*5000}
try:native_origin_from_session(SimpleNamespace(file=Oversized()));raise AssertionError('oversized accepted')
except ImageFailure as e:assert str(e)=='NATIVE_ORIGIN_UNAVAILABLE'
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=app,
        check=True,
        capture_output=True,
        timeout=15,
    )
