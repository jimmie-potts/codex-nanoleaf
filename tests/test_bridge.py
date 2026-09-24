import concurrent.futures
import contextlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / 'bridge/bridge.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def decode(payload):
    values = list(map(int, payload['write']['animData'].split()))
    count, offset, panels = values[0], 1, {}
    for _ in range(count):
        panel, frames = values[offset:offset+2]
        offset += 2
        panels[panel] = [values[i:i+5] for i in range(offset, offset+frames*5, 5)]
        offset += frames * 5
    assert offset == len(values)
    return panels


class Clock:
    def __init__(self):
        self.value = 1000.0
    def now(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.clock = Clock()
        self.config = {'ip': '192.168.1.207', 'token': 'test',
                       'line_groups': [[100+i*2,101+i*2] for i in range(15)],
                       'line_positions': [[i*10,0] for i in range(15)]}
        (self.path/'config.json').write_text(json.dumps({'ip': self.config['ip'], 'token': 'test'}))
        (self.path/'layout.json').write_text(json.dumps({k:self.config[k] for k in ('line_groups','line_positions')}))
        self.sent = []
        self.unread = set()

    def send(self, config, snapshot, instant, loop):
        self.sent.append((list(snapshot), instant, loop))

    def drain(self, sleep=None, send=None):
        b.run_worker(self.path, send=send or self.send, sleep=sleep or self.clock.sleep,
                     now=self.clock.now, read_unread=lambda:self.unread, scene_factory=None)

    def event(self, name, session='a', turn='1', defer=False, **extra):
        b.handle_event(self.path, {'hook_event_name':name,'session_id':session,'turn_id':turn,
                                 'prompt':'PRIVATE CONTENT',**extra}, now=self.clock.now,
                       launch=lambda directory: None if defer else self.drain())

    def query(self, sql):
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            return db.execute(sql).fetchall()

    def statuses(self):
        return dict(self.query('SELECT id,status FROM sessions'))

    def snapshot(self):
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            return b.dashboard(db,self.config,self.clock.now())

    def test_render_returns_the_successfully_accepted_output_and_timing(self):
        calls=[]
        config={**self.config,'_mode':'work','_now':self.clock.now}
        snapshot=[('working',1000.0)]+[None]*14
        def request(cfg,method,endpoint,payload=None):
            calls.append((method,endpoint,json.loads(json.dumps(payload))))
            self.clock.sleep(.25 if endpoint=='/effects' else .4)
        config['_controller_request']=request

        receipt=b.render(config,snapshot,1000.0,True)

        self.assertEqual([call[:2] for call in calls],[('PUT','/effects'),('PUT','/state')])
        self.assertEqual(receipt['effect'],calls[0][2])
        self.assertEqual(receipt['lineGroups'],self.config['line_groups'])
        self.assertEqual(receipt['mode'],'work')
        self.assertEqual(receipt['brightness'],30)
        self.assertTrue(receipt['loop'])
        self.assertEqual(receipt['animationEpochMs'],1_000_000)
        self.assertEqual(receipt['sendStartedAtMs'],1_000_000)
        self.assertEqual(receipt['effectAcceptedAtMs'],1_000_250)
        self.assertEqual(receipt['acceptedAtMs'],1_000_650)

    def test_render_returns_completion_comet_receipt(self):
        calls=[]
        config={**self.config,'_mode':'work','_comet':{'source':7,'started':1998.0},
                '_now':lambda:2000.5}
        config['_controller_request']=lambda cfg,method,endpoint,payload=None: calls.append((endpoint,payload))

        receipt=b.render(config,[None]*15,2000.0,False)

        self.assertEqual([endpoint for endpoint,_ in calls],['/effects','/state'])
        self.assertEqual(receipt['effect'],calls[0][1])
        self.assertEqual(receipt['lineGroups'],self.config['line_groups'])
        self.assertEqual(receipt['mode'],'work')
        self.assertEqual(receipt['brightness'],30)
        self.assertFalse(receipt['loop'])
        self.assertEqual(receipt['animationEpochMs'],2_000_000)
        self.assertEqual(receipt['acceptedAtMs'],2_000_500)
        self.assertTrue(receipt['effect']['write']['animData'])

    def test_update_display_keeps_only_the_last_fully_successful_receipt(self):
        receipt={'apiVersion':'1.0','deviceId':'wall','effect':{'write':{'animData':'1 100 1 0'}},
                 'lineGroups':[[100,101]],'mode':'work','brightness':30,'loop':True,
                 'animationEpochMs':1_000_000,'acceptedAtMs':1_000_650}
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            b.update_display(db,self.config,[('working',1000.0)]+[None]*14,1000.0,True,
                              send=lambda *_:receipt)
        saved=json.loads(self.query("SELECT value FROM meta WHERE key='rendering_receipt'")[0][0])
        self.assertEqual(saved,receipt)

        def fail(*_):
            raise OSError('Device unavailable')
        with self.assertRaises(OSError):
            with contextlib.closing(b.connect_state(self.path)) as db,db:
                b.update_display(db,self.config,[('blocked',1001.0)]+[None]*14,1001.0,False,send=fail)
        self.assertEqual(json.loads(self.query("SELECT value FROM meta WHERE key='rendering_receipt'")[0][0]),receipt)

    def test_update_display_persists_the_accepted_completion_comet(self):
        calls=[]
        config={**self.config,'_mode':'work','_comet':{'source':7,'started':1998.0},
                '_now':lambda:2000.5}
        config['_controller_request']=lambda cfg,method,endpoint,payload=None: calls.append((endpoint,payload))
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            b.update_display(db,config,[None]*15,2000.0,False)

        receipt=json.loads(self.query("SELECT value FROM meta WHERE key='rendering_receipt'")[0][0])
        self.assertEqual(receipt['effect'],calls[0][1])
        self.assertEqual(receipt['lineGroups'],self.config['line_groups'])
        self.assertEqual(receipt['mode'],'work')
        self.assertFalse(receipt['loop'])
        self.assertEqual(receipt['animationEpochMs'],2_000_000)
        self.assertEqual(receipt['acceptedAtMs'],2_000_500)

    def test_first_working_pulse_radiates_then_only_local_loop(self):
        self.event('UserPromptSubmit')
        self.assertEqual([loop for _,_,loop in self.sent], [False,True])
        for actual, expected in zip([t for _,t,_ in self.sent], [1000,1002]):
            self.assertAlmostEqual(actual,expected)
        snap,t,loop = self.sent[-1]
        panels = decode(b.effect_payload(self.config,snap,t,loop))
        source = next(i for i,activity in enumerate(snap) if activity)
        for i,pair in enumerate(self.config['line_groups']):
            colors = {tuple(frame[:3]) for frame in panels[pair[0]]}
            if i==source:
                self.assertIn(b.COLORS['working'],colors)
                self.assertIn((0,51,0),colors)
                self.assertNotIn(b.BASELINE,colors)
            else:
                self.assertEqual(colors,{b.BASELINE})

    def test_radiation_spreads_by_distance_from_task_in_both_directions(self):
        snapshot = [None]*15
        snapshot[7] = ('working',0)
        delays = [b.travel_delays(self.config,i) for i in range(15)]
        self.assertEqual(delays[7][0],delays[7][14])
        self.assertLess(delays[7][6],delays[7][0])
        self.assertEqual(b.pixel_color(snapshot,7,0.5,delays), b.COLORS['working'])
        self.assertEqual(b.pixel_color(snapshot,0,0.5,delays), b.BASELINE)
        for target in (0,14):
            self.assertEqual(b.pixel_color(snapshot,target,1.3,delays),b.COLORS['working'])
            for later_pulse in (3.3,5.3):
                self.assertEqual(b.pixel_color(snapshot,target,later_pulse,delays),b.BASELINE)
        self.assertEqual(b.pixel_color(snapshot,7,2.5,delays),b.COLORS['working'])

    def test_each_color_gets_one_radiating_pulse(self):
        self.event('UserPromptSubmit')
        self.event('PreToolUse',tool_name='request_user_input_async',tool_use_id='q')
        self.event('PermissionRequest',tool_name='Bash')
        self.assertEqual(self.statuses()['a'],'blocked')
        self.assertEqual(len(self.sent),6)
        self.assertEqual([self.sent[i][0][0][0] for i in (0,2,4)],['working','question','blocked'])
        for i in (0,2,4):
            self.assertEqual([x[2] for x in self.sent[i:i+2]],[False,True])

    def test_tool_progress_does_not_restart_flashes_or_send_more_effects(self):
        self.event('UserPromptSubmit')
        epoch = self.query('SELECT started FROM activity')
        for _ in range(8):
            self.event('PreToolUse',tool_name='Bash')
            self.event('PostToolUse',tool_name='Bash')
        self.assertEqual(self.query('SELECT started FROM activity'),epoch)
        self.assertEqual(len(self.sent),2)

    def test_finished_and_interrupted_tasks_return_to_blue_not_off(self):
        self.event('UserPromptSubmit')
        self.event('Stop')
        self.assertEqual(self.sent[-1][0],[None]*15)
        self.event('UserPromptSubmit',turn='2')
        self.event('Interrupt',turn='2')
        self.assertEqual(self.sent[-1][0],[None]*15)
        calls=[]
        original=b.light_request
        b.light_request=lambda *args:calls.append(args)
        try:
            b.render(self.config,[None]*15,0,True)
        finally:
            b.light_request=original
        self.assertEqual(calls[-1][3]['on'],{'value':True})
        for frames in decode(calls[0][3]).values():
            self.assertEqual(tuple(frames[0][:3]),b.BASELINE)

    def test_async_question_is_yellow_while_other_work_continues(self):
        self.event('UserPromptSubmit')
        self.event('PreToolUse',tool_name='functions.request_user_input_async',tool_use_id='q')
        self.event('PostToolUse',tool_name='functions.request_user_input_async',tool_use_id='q')
        self.event('PostToolUse',tool_name='Bash')
        self.assertEqual(self.statuses()['a'],'question')
        self.assertEqual(len(self.sent),4)

    def test_unanswered_question_becomes_red_when_response_stops(self):
        self.event('UserPromptSubmit')
        self.event('PreToolUse',tool_name='request_user_input_async',tool_use_id='q')
        self.event('Stop')
        self.assertEqual(self.statuses()['a'],'blocked')
        self.event('PostToolUse',tool_name='Bash')
        self.assertEqual(self.statuses()['a'],'blocked')
        self.event('UserPromptSubmit',turn='2')
        self.assertEqual(self.statuses()['a'],'working')
        self.assertEqual(self.query('SELECT * FROM waits'),[])

    def test_blocking_input_is_red_until_its_own_result_returns(self):
        self.event('UserPromptSubmit')
        self.event('PreToolUse',tool_name='request_user_input',tool_use_id='one')
        self.event('PreToolUse',tool_name='request_user_input',tool_use_id='two')
        self.event('PostToolUse',tool_name='request_user_input',tool_use_id='one')
        self.assertEqual(self.statuses()['a'],'blocked')
        self.event('PostToolUse',tool_name='request_user_input',tool_use_id='two')
        self.assertEqual(self.statuses()['a'],'working')

    def test_permission_block_has_priority_over_nonblocking_question(self):
        self.event('UserPromptSubmit')
        self.event('PreToolUse',tool_name='request_user_input_async',tool_use_id='q')
        self.event('PermissionRequest',tool_name='Bash')
        self.event('PostToolUse',tool_name='apply_patch')
        self.assertEqual(self.statuses()['a'],'blocked')
        self.event('PostToolUse',tool_name='Bash')
        self.assertEqual(self.statuses()['a'],'question')

    def test_duplicate_and_stale_events_cannot_restart_finished_task(self):
        self.event('UserPromptSubmit')
        self.event('UserPromptSubmit',turn='2')
        self.event('Stop',turn='1')
        self.assertEqual(self.statuses()['a'],'working')
        self.event('Stop',turn='2')
        count=len(self.sent)
        self.event('Stop',turn='2')
        self.event('PermissionRequest',turn='2',tool_name='Bash')
        self.assertEqual(self.statuses()['a'],'ended')
        self.assertEqual(len(self.sent),count)

    def test_state_change_interrupts_animation_without_resetting_other_task_epoch(self):
        self.event('UserPromptSubmit','a',defer=True)
        self.event('UserPromptSubmit','b',defer=True)
        original=dict(self.query('SELECT session,started FROM activity'))
        changed=False
        def during(seconds):
            nonlocal changed
            self.clock.sleep(seconds)
            if not changed:
                changed=True
                self.event('PermissionRequest','b',tool_name='Bash',defer=True)
        self.drain(sleep=during)
        self.assertLessEqual(self.sent[1][1]-self.sent[0][1],0.25)
        self.assertEqual(dict(self.query('SELECT session,started FROM activity'))['a'],original['a'])
        self.assertEqual(self.statuses(),{'a':'working','b':'blocked'})

    def test_other_task_start_does_not_restore_old_radiation(self):
        self.event('UserPromptSubmit','a')
        epoch=dict(self.query('SELECT session,started FROM activity'))['a']
        self.event('UserPromptSubmit','b')
        self.assertEqual(dict(self.query('SELECT session,started FROM activity'))['a'],epoch)
        self.assertGreaterEqual(self.sent[-1][1]-epoch,4)

    def test_task_slots_are_stable_and_completed_slots_can_be_reused(self):
        for i in range(15):
            self.event('UserPromptSubmit',str(i),defer=True)
        self.drain()
        assigned=dict(self.query('SELECT session,slot FROM slots'))
        self.event('Stop','3')
        self.event('UserPromptSubmit','new')
        current=dict(self.query('SELECT session,slot FROM slots'))
        self.assertEqual(current['new'],assigned['3'])
        for session,slot in assigned.items():
            if session!='3': self.assertEqual(current[session],slot)

    def test_concurrent_tasks_never_share_a_slot(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(self.event,'UserPromptSubmit',str(i),defer=True) for i in range(17)]
            for future in futures: future.result()
        self.drain()
        slots=self.query('SELECT slot FROM slots')
        self.assertEqual(len(slots),15)
        self.assertEqual(len(set(slots)),15)
        self.assertEqual(len(self.statuses()),17)

    def test_failed_initialization_closes_connection(self):
        with contextlib.closing(sqlite3.connect(self.path/'status.sqlite')) as db, db:
            db.execute('CREATE TABLE map_settings (id INTEGER PRIMARY KEY)')
        connections = []
        connect = sqlite3.connect

        def tracked_connect(*args, **kwargs):
            db = connect(*args, **kwargs)
            connections.append(db)
            self.addCleanup(db.close)
            return db

        with patch.object(b.sqlite3, 'connect', tracked_connect):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'map_settings'):
                b.connect_state(self.path)
        self.assertEqual(len(connections), 1)
        with self.assertRaisesRegex(sqlite3.ProgrammingError, 'closed'):
            connections[0].execute('SELECT 1')

    def test_failed_initialization_rolls_back_partial_schema(self):
        with contextlib.closing(sqlite3.connect(self.path/'status.sqlite')) as db, db:
            db.execute('CREATE TABLE map_settings (id INTEGER PRIMARY KEY)')
        with self.assertRaisesRegex(sqlite3.OperationalError, 'map_settings'):
            b.connect_state(self.path)
        with contextlib.closing(sqlite3.connect(self.path/'status.sqlite')) as db:
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        self.assertEqual(tables, [('map_settings',)])

    def test_failed_send_keeps_status_for_retry_on_next_event(self):
        self.event('UserPromptSubmit',defer=True)
        def fail(*args): raise RuntimeError('offline')
        with self.assertRaises(RuntimeError): self.drain(send=fail)
        self.assertEqual(self.statuses()['a'],'working')
        self.event('PostToolUse',tool_name='Bash')
        self.assertTrue(self.sent[-1][2])

    def test_worker_recovers_if_finite_animation_was_interrupted_by_failure(self):
        self.event('UserPromptSubmit',defer=True)
        def fail_after_first(*args):
            if self.sent: raise RuntimeError('offline')
            self.send(*args)
        with self.assertRaises(RuntimeError): self.drain(send=fail_after_first)
        self.assertEqual(self.query("SELECT value FROM meta WHERE key='rendering'"),[('1',)])
        self.event('PostToolUse',tool_name='Bash')
        self.assertTrue(self.sent[-1][2])
        self.assertEqual(self.query("SELECT value FROM meta WHERE key='rendering'"),[])

    def test_only_one_worker_and_state_updates_remain_available(self):
        self.event('UserPromptSubmit',defer=True)
        started,release=threading.Event(),threading.Event()
        def pause(seconds):
            started.set()
            if not release.wait(3): raise RuntimeError('test timed out')
            self.clock.sleep(seconds)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.drain,sleep=pause)
            try:
                self.assertTrue(started.wait(2))
                pool.submit(self.drain).result(timeout=1)
                self.event('Stop',defer=True)
            finally: release.set()
            first.result(timeout=2)
        self.assertEqual(self.sent[-1][0],[None]*15)

    def test_session_end_clears_activity_and_waits(self):
        self.event('UserPromptSubmit')
        self.event('PermissionRequest',tool_name='Bash')
        self.event('SessionEnd',turn='')
        for table in ('sessions','activity','slots','waits'):
            self.assertEqual(self.query('SELECT * FROM '+table),[])
        self.assertEqual(self.sent[-1][0],[None]*15)

    def test_migration_keeps_task_assignments_and_removes_old_notifications(self):
        with contextlib.closing(sqlite3.connect(self.path/'status.sqlite')) as db,db:
            db.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY, turn TEXT, status TEXT, updated REAL)')
            db.execute("INSERT INTO sessions VALUES ('existing','t','approval',1)")
            db.execute('CREATE TABLE slots(session TEXT PRIMARY KEY, slot INTEGER UNIQUE)')
            db.execute("INSERT INTO slots VALUES ('existing',4)")
            db.execute('CREATE TABLE signals(id INTEGER PRIMARY KEY, session TEXT,turn TEXT,kind TEXT)')
            db.execute("INSERT INTO signals VALUES (1,'old','turn','ended')")
        self.assertEqual(self.statuses()['existing'],'blocked')
        self.assertEqual(self.query('SELECT session,slot FROM slots'),[('existing',4)])
        self.assertEqual(self.query('SELECT * FROM signals'),[])
        self.assertEqual(len(self.query('SELECT * FROM activity')),1)

    def test_no_prompt_or_question_content_is_stored(self):
        self.event('UserPromptSubmit')
        self.event('PreToolUse',tool_name='request_user_input_async',tool_use_id='q',
                   tool_input={'question':'PRIVATE QUESTION'})
        contents=(self.path/'status.sqlite').read_bytes()
        self.assertNotIn(b'PRIVATE CONTENT',contents)
        self.assertNotIn(b'PRIVATE QUESTION',contents)

    def test_unknown_events_are_ignored(self):
        self.event('Unknown')
        self.event('Stop',session='')
        self.event('UserPromptSubmit',turn=None)
        self.assertEqual(self.sent,[])

    def test_both_zones_match_and_animation_has_two_second_period(self):
        snapshot=[None]*15
        snapshot[7]=('question',1000)
        for instant,loop in ((1000,False),(1002,True)):
            payload=b.effect_payload(self.config,snapshot,instant,loop)
            self.assertEqual(payload['write']['loop'],loop)
            panels=decode(payload)
            self.assertEqual(len(panels),30)
            for pair in self.config['line_groups']:
                self.assertEqual(panels[pair[0]],panels[pair[1]])
                self.assertEqual(sum(frame[-1] for frame in panels[pair[0]]),20)
                self.assertTrue(all(frame[-1]>=1 for frame in panels[pair[0]]))
                self.assertNotIn([0,0,0],[frame[:3] for frame in panels[pair[0]]])

    def test_fifteen_physical_lines_are_paired_from_real_layout(self):
        layout=json.loads((ROOT/'tests/fixtures/lines-layout.json').read_text())
        groups=b.pair_lines(layout)
        self.assertEqual(len(groups),15)
        expected={p['panelId'] for p in layout['layout']['positionData'] if p['shapeType']==18}
        self.assertEqual({p for pair in groups for p in pair},expected)

    def test_red_radiation_has_priority_when_different_colors_overlap(self):
        snapshot=[('working',0),('blocked',0)]+[None]*13
        delays=[b.travel_delays(self.config,i) for i in range(15)]
        rgb=b.pixel_color(snapshot,0,0.5,delays)
        self.assertEqual(rgb,b.COLORS['blocked'])

    def test_merge_preserves_other_hooks_and_uninstall(self):
        original={'description':'keep','hooks':{'Stop':[{'hooks':[{'type':'command','command':'echo existing'}]}]}}
        merged=b.merge_hooks(original,'python3 bridge.py hook',windows_command='windows')
        self.assertEqual(b.merge_hooks(merged,'python3 bridge.py hook',windows_command='windows'),merged)
        self.assertEqual(b.merge_hooks(merged,'',remove=True),original)

    def test_unread_completion_pulses_blue_until_desktop_flag_clears(self):
        self.event('UserPromptSubmit')
        self.unread={'a'}
        self.event('Stop',defer=True)
        completed=self.clock.now()
        count=len(self.sent)
        def open_task(seconds):
            self.clock.sleep(seconds)
            if self.clock.now() >= completed+17:
                self.unread=set()
        self.drain(sleep=open_task)
        playback=self.sent[count:]
        self.assertEqual([loop for _,_,loop in playback[:2]],[False,True])
        self.assertEqual(playback[1][0][0][0],'unread')
        self.assertGreaterEqual(playback[-1][1]-completed,17)
        self.assertEqual(playback[-1][0],[None]*15)
        self.assertEqual(self.statuses()['a'],'ended')

    def test_unread_flag_can_arrive_after_stop_without_losing_notification(self):
        self.event('UserPromptSubmit')
        self.event('Stop',defer=True)
        completed=self.clock.now()
        observed=False
        def late_flag(seconds):
            nonlocal observed
            self.clock.sleep(seconds)
            age=self.clock.now()-completed
            if 2 <= age < 15:
                self.unread={'a'}
            elif age>=15:
                observed=self.statuses()['a']=='unread'
                self.unread=set()
        self.drain(sleep=late_flag)
        self.assertTrue(observed)
        self.assertEqual(self.statuses()['a'],'ended')

    def test_unavailable_read_state_does_not_acknowledge_completion(self):
        self.event('UserPromptSubmit')
        self.event('Stop',defer=True)
        self.clock.sleep(60)
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            b.reconcile_read_state(db,None,self.clock.now())
        self.assertEqual(self.statuses()['a'],'unread')

    def test_missing_completion_receipt_recovers_without_replaying_or_skipping_settle(self):
        self.event('UserPromptSubmit')
        self.event('Stop',defer=True)
        completed=self.clock.now()
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            # Legacy rollback restores task status but discards old receipts/comets.
            db.execute('DELETE FROM receipts')
            db.execute('DELETE FROM comets')
            activity=db.execute('SELECT * FROM activity').fetchall()
            b.reconcile_read_state(db,None,completed+60)
            self.assertEqual(db.execute('SELECT * FROM receipts').fetchall(),[])
            self.assertEqual(db.execute("SELECT status FROM sessions WHERE id='a'").fetchone(),('unread',))
            b.reconcile_read_state(db,set(),completed+b.READ_SETTLE_SECONDS-.1)
            self.assertEqual(db.execute('SELECT * FROM receipts').fetchall(),[('a','1',completed,0)])
            self.assertEqual(db.execute('SELECT * FROM activity').fetchall(),activity)
            b.reconcile_read_state(db,{'a'},completed+b.READ_SETTLE_SECONDS)
            self.assertEqual(db.execute('SELECT observed FROM receipts').fetchone(),(1,))
            b.reconcile_read_state(db,None,completed+60)
            self.assertEqual(db.execute("SELECT status FROM sessions WHERE id='a'").fetchone(),('unread',))
            b.reconcile_read_state(db,set(),completed+61)
            self.assertEqual(db.execute("SELECT status FROM sessions WHERE id='a'").fetchone(),('ended',))
            self.assertEqual(db.execute('SELECT * FROM receipts').fetchall(),[])
            self.assertEqual(db.execute('SELECT * FROM comets').fetchall(),[])

    def test_runtime_closing_does_not_clear_unread_completion(self):
        self.event('UserPromptSubmit')
        self.unread={'a'}
        self.event('Stop',defer=True)
        self.event('SessionEnd',turn='',defer=True)
        self.assertEqual(self.statuses()['a'],'unread')
        self.assertEqual(len(self.query('SELECT * FROM receipts')),1)

    def test_blue_completion_pulses_locally_without_legacy_wave(self):
        snapshot=[('unread',0)]+[None]*14
        delays=[b.travel_delays(self.config,i) for i in range(15)]
        self.assertEqual(b.pixel_color(snapshot,0,0.5,delays),b.BASELINE)
        self.assertEqual(b.pixel_color(snapshot,0,1.5,delays),(5,12,51))
        rgb=b.pixel_color(snapshot,14,1,delays)
        self.assertEqual(rgb,b.BASELINE)
        for later_pulse in (3,5):
            self.assertEqual(b.pixel_color(snapshot,14,later_pulse,delays),b.BASELINE)

    def test_assigned_lines_keep_their_status_hue_at_every_pulse_brightness(self):
        for status, bright in b.COLORS.items():
            with self.subTest(status=status):
                snapshot=[(status,0)]+[None]*14
                panels=decode(b.effect_payload(self.config,snapshot,100,True))
                colors=[tuple(frame[:3]) for frame in panels[100]]
                self.assertIn(bright,colors)
                self.assertIn(tuple(round(channel*0.2) for channel in bright),colors)
                for color in colors:
                    scale=max(color)/max(bright)
                    self.assertGreaterEqual(scale,0.2)
                    for actual,channel in zip(color,bright):
                        self.assertAlmostEqual(actual,channel*scale,delta=1)
                for line in range(1,15):
                    self.assertEqual({tuple(f[:3]) for f in panels[100+line*2]}, {b.BASELINE})

    def test_concurrent_local_statuses_keep_independent_hues(self):
        snapshot=[(status,0) for status in b.COLORS]+[None]*11
        panels=decode(b.effect_payload(self.config,snapshot,100.7,True))
        for line,status in enumerate(b.COLORS):
            colors={tuple(f[:3]) for f in panels[100+line*2]}
            self.assertIn(b.COLORS[status],colors)
            if status!='unread':
                self.assertTrue(all(color[2]==0 for color in colors))

    def test_source_keeps_status_color_during_outward_and_following_local_pulses(self):
        for status,bright in b.COLORS.items():
            snapshot=[(status,0)]+[None]*14
            delays=[b.travel_delays(self.config,i) for i in range(15)]
            for cycle in range(3):
                self.assertEqual(b.pixel_color(snapshot,0,cycle*2+1.9,delays),
                                 tuple(round(channel*0.2) for channel in bright))

    def test_read_indicator_is_read_only_and_malformed_state_is_not_seen(self):
        state=self.path/'desktop.json'
        value={'electron-persisted-atom-state':{'unread-thread-ids-by-host-v1':{'local':['a']}}}
        state.write_text(json.dumps(value))
        read=b.unread_reader({'desktop_state_path':str(state)})
        before=state.read_bytes()
        self.assertEqual(read(),{'a'})
        self.assertEqual(state.read_bytes(),before)
        state.write_text('{')
        self.assertIsNone(read())
        value['electron-persisted-atom-state']['unread-thread-ids-by-host-v1']['local']=[]
        state.write_text(json.dumps(value))
        self.assertEqual(read(),set())

    def test_current_read_indicator_refreshes_and_overrides_legacy(self):
        state=self.path/'desktop.json'
        value={'electron-thread-read-state-v1':{'version':1,'unreadByIdentity':{
            'local':{'account-a':['a','b'],'account-b':['b']},'remote':{'account-c':['c']}}},
            'electron-persisted-atom-state':{'unread-thread-ids-by-host-v1':{'local':['old']}}}
        state.write_text(json.dumps(value))
        read=b.unread_reader({'desktop_state_path':str(state)})
        original=state.read_bytes()
        self.assertEqual(read(),{'a','b','c'})
        self.assertEqual(read(),{'a','b','c'})
        self.assertEqual(state.read_bytes(),original)
        value['electron-thread-read-state-v1']['unreadByIdentity']={}
        state.write_text(json.dumps(value))
        self.assertEqual(read(),set())

    def test_current_read_evidence_releases_occupied_lines(self):
        state=self.path/'desktop.json'
        state.write_text(json.dumps({'electron-thread-read-state-v1':{
            'version':1,'unreadByIdentity':{'local':{'account':['old']}}}}))
        read=b.unread_reader({'desktop_state_path':str(state)})
        config=dict(self.config,line_groups=self.config['line_groups'][:1],
                    line_positions=self.config['line_positions'][:1])
        self.event('UserPromptSubmit',session='old',defer=True)
        self.event('Stop',session='old',defer=True)
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            b.dashboard(db,config,self.clock.now())
        self.event('UserPromptSubmit',session='new',defer=True)
        with contextlib.closing(b.connect_state(self.path)) as db,db:
            b.reconcile_read_state(db,read(),self.clock.now())
            b.dashboard(db,config,self.clock.now())
            self.assertEqual(db.execute("SELECT session FROM slots WHERE device='wall'").fetchall(),[('old',)])
            state.write_text(json.dumps({'electron-thread-read-state-v1':{
                'version':1,'unreadByIdentity':{'local':{'account':[]}}}}))
            b.reconcile_read_state(db,read(),self.clock.now()+b.READ_SETTLE_SECONDS)
            b.dashboard(db,config,self.clock.now()+b.READ_SETTLE_SECONDS)
            self.assertEqual(db.execute("SELECT status FROM sessions WHERE id='old'").fetchone(),('ended',))
            self.assertEqual(db.execute("SELECT session FROM slots WHERE device='wall'").fetchall(),[('new',)])

    def test_invalid_current_read_marker_never_uses_old_empty_indicator(self):
        state=self.path/'desktop.json'
        read=b.unread_reader({'desktop_state_path':str(state)})
        self.assertIsNone(read())
        invalid=[None,[],{}, {'version':2,'unreadByIdentity':{}},
                 {'version':True,'unreadByIdentity':{}}, {'version':1,'unreadByIdentity':[]},
                 {'version':1,'unreadByIdentity':{'local':[]}},
                 *({'version':1,'unreadByIdentity':{'local':{'account':value}}}
                   for value in (None,'a',{},['a',None],['a',1],['']))]
        for marker in invalid:
            with self.subTest(marker=marker):
                state.write_text(json.dumps({'electron-thread-read-state-v1':{
                    'version':1,'unreadByIdentity':{'local':{'account':['a']}}}}))
                self.assertEqual(read(),{'a'})
                state.write_text(json.dumps({'electron-thread-read-state-v1':marker,
                    'electron-persisted-atom-state':{'unread-thread-ids-by-host-v1':{'local':[]}}}))
                original=state.read_bytes()
                self.assertIsNone(read())
                self.assertIsNone(read())
                self.assertEqual(state.read_bytes(),original)
        for raw in ('{','[]','null'):
            state.write_text(raw)
            self.assertIsNone(read())
        state.unlink()
        self.assertIsNone(read())

    def test_invalid_legacy_read_ids_are_unavailable(self):
        state=self.path/'desktop.json'
        for ids in ([''],['a',None],['a',1]):
            with self.subTest(ids=ids):
                state.write_text(json.dumps({'electron-persisted-atom-state':{
                    'unread-thread-ids-by-host-v1':{'local':ids}}}))
                self.assertIsNone(b.unread_reader({'desktop_state_path':str(state)})())


if __name__=='__main__':
    unittest.main()
