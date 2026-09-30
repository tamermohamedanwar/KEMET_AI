from pathlib import Path
from app.services.asset_binding_gate import asset_binding_gate
from app.services.provider_capacity_gate import provider_capacity_gate
from app.services.wan_backend_adapter import wan_backend_adapter

def test_asset_gate_binds_exact_digest(tmp_path):
    p=tmp_path/'ref.png'; p.write_bytes(b'PNG-REFERENCE')
    from hashlib import sha256
    digest=sha256(p.read_bytes()).hexdigest()
    out=asset_binding_gate.inspect(organization_id=1,project_id='p',references=[{'id':'younes','version':1,'uri':str(p),'digest':digest}])
    assert out['status']=='BOUND' and out['references'][0]['actual_digest']==digest

def test_asset_gate_blocks_missing():
    out=asset_binding_gate.inspect(organization_id=1,project_id='p',references=[{'id':'world','version':1,'uri':'/missing/world.png','digest':'x'}])
    assert out['status']=='BLOCKED' and 'reference_asset_missing' in out['references'][0]['errors']

def test_capacity_gate_requires_live_capacity():
    out=provider_capacity_gate.evaluate(providers=[{'provider_id':'wan2_2_remote','capabilities':['VIDEO_GENERATION'],'configured':True,'healthy':True,'available':True,'capacity':{'in_flight':1,'max_concurrency':1}}],required_capabilities=['VIDEO_GENERATION'])
    assert out['status']=='BLOCKED'

def test_capacity_gate_ready_provider():
    out=provider_capacity_gate.evaluate(providers=[{'provider_id':'wan2_2_remote','capabilities':['VIDEO_GENERATION'],'configured':True,'healthy':True,'available':True,'capacity':{'in_flight':0,'max_concurrency':1,'queue_depth':0,'max_queue_depth':10}}],required_capabilities=['VIDEO_GENERATION'])
    assert out['status']=='READY'

def test_wan_backend_requires_asset_gate():
    try: wan_backend_adapter.build_job(organization_id=1,shot={'shot_id':'s','canonical_shot_digest':'d'},asset_gate={'status':'BLOCKED'})
    except ValueError as e: assert str(e)=='asset_binding_gate_required'
    else: raise AssertionError('expected gate')

def test_wan_backend_requires_execution_gate():
    out=wan_backend_adapter.execute(job={'organization_id':1,'shot_id':'s','canonical_shot_digest':'d','digest':'job'},approval={'approved':True})
    assert out['status']=='blocked' and out['error']=='execution_gate_required'

def test_wan_backend_requires_worker_secret_after_gate(monkeypatch):
    monkeypatch.setenv('KEMET_WAN_WORKER_URL','https://worker.example')
    monkeypatch.delenv('KEMET_WAN_WORKER_SECRET', raising=False)
    out=wan_backend_adapter.execute(job={'organization_id':1,'shot_id':'s','canonical_shot_digest':'d','digest':'job'},approval={'approved':True,'execution_gate':{'allowed':True}})
    assert out['status']=='blocked' and out['error']=='wan_remote_worker_secret_not_configured'
