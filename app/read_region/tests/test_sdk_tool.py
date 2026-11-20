import subprocess
import sys
from pathlib import Path


def test_sdk_tool_returns_real_png_blob_and_rejects_raw_dict():
    root = Path(__file__).resolve().parents[1]
    code = r"""
import io,json,os
from PIL import Image
from dify_plugin.entities.tool import ToolRuntime
from dify_plugin.core.runtime import Session
from dify_plugin.file.file import File
import tools.read_region as module
image=Image.new('RGB',(80,60),'red');out=io.BytesIO();image.save(out,format='PNG')
module.download=lambda *a:out.getvalue()
from vision_core.fetch import Origin
module.native_origin_from_session=lambda session:Origin('http','native.example.invalid',5001)
os.environ['DIFY_INNER_API_URL']='http://native.example.invalid:5001'
file=File(url='not-exposed',mime_type='image/png',filename='private-filename-canary.png',type='image',size=len(out.getvalue()))
tool=module.ReadRegionTool(runtime=ToolRuntime(credentials={},user_id='synthetic',session_id=None),session=Session.empty_session())
messages=list(tool._invoke({'source_image':file,'x_min':.25,'y_min':.25,'x_max':.75,'y_max':.75}))
assert len(messages)==2
assert messages[0].message.json_object['output_size']=={'width':40,'height':30}
with Image.open(io.BytesIO(messages[1].message.blob)) as decoded:assert decoded.size==(40,30)
assert 'private-filename-canary' not in str(messages[0])
try:list(tool._invoke({'source_image':{'__dify__file__':True,'url':'file:///etc/passwd'}}));raise AssertionError('raw dict accepted')
except ValueError as e:assert str(e)=='INVALID_NATIVE_FILE'
"""
    subprocess.run(
        [sys.executable, "-c", code], cwd=root, check=True, capture_output=True
    )
