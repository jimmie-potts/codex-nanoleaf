"""Run the real worker CLI with synthetic state and an injected fake light transport."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_controller_controls as controls
from test_bridge import b

fixture=controls.ControlsTest()
fixture.setUp()
try:
    fixture.mode('free')
    fixture.run_worker()
    request,(code,receipt)=fixture.command({'kind':'brightness.set','percent':37})
    assert code==202
    sys.argv=['bridge.py','worker','--state-dir',str(fixture.directory)]
    b.main(request=fixture.device.request)
    assert fixture.app.admit(fixture.token,request)[1]['outcome']=='sent'
finally:
    fixture.doCleanups()
