import contextlib
import copy
import unittest
import test_scene_restore as fixtures
from test_bridge import b, decode
import database
import modes
import store


class CometTest(unittest.TestCase):
    setUp = fixtures.SceneTest.setUp
    event = fixtures.SceneTest.event
    query = fixtures.SceneTest.query
    run_worker = fixtures.SceneTest.run_worker

    def complete(self, session='a'):
        self.event('UserPromptSubmit', session)
        self.event('Stop', session)
        self.unread.add(session)

    def prepare(self):
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            b.prune_comets(db, self.clock.now(), store.control_state(db)['mode'])
            snapshot = b.dashboard(db, self.config, self.clock.now())
            return snapshot, b.current_comet(db, self.clock.now())

    def mode(self, mode):
        modes.set_mode(self.directory, mode, launch=lambda _: None, now=self.clock.now)

    def test_geometry_head_tail_duration_and_zone_pairs(self):
        cfg = dict(self.config, _comet={'source': 0, 'started': 1000}, _mode='work')
        snapshot = [('working', 990)]*15
        delays = [b.travel_delays(cfg, i) for i in range(15)]
        base = (0, 51, 0)
        color = lambda i,t: b.comet_color(cfg,snapshot,i,t,delays,base)
        self.assertEqual(color(0,1000.05), (255,255,255))
        self.assertEqual(color(14,1001.45), (255,255,255))
        self.assertEqual(color(14,1001.3), base)
        self.assertEqual(color(14,1002), base)
        tail = color(14,1001.75)
        self.assertGreater(tail[2], tail[0])
        self.assertNotEqual(tail, base)
        payload = b.effect_payload(cfg,snapshot,1000,True)
        self.assertFalse(payload['write']['loop'])
        panels = decode(payload)
        for pair in cfg['line_groups']:
            self.assertEqual(panels[pair[0]],panels[pair[1]])
            self.assertEqual(sum(f[4] for f in panels[pair[0]]),20)
            self.assertEqual(len(panels[pair[0]]),20)

    def test_protect_red_yellow_lines_and_outward_waves(self):
        cfg = dict(self.config, _comet={'source': 0, 'started': 1000})
        snapshot = [None]*15
        snapshot[0] = ('blocked',999)
        snapshot[1] = ('question',999)
        snapshot[14] = ('blocked',999.6)
        delays = [b.travel_delays(cfg, i) for i in range(15)]
        for target, instant in [(0,1000.05),(1,1000.15),(8,1000.86)]:
            base = b.pixel_color(snapshot,target,instant,delays)
            self.assertEqual(b.comet_color(cfg,snapshot,target,instant,delays,base),base)
        self.assertNotEqual(b.pixel_color(snapshot,8,1000.86,delays),b.BASELINE)

    def test_completions_queue_in_order_and_duplicate_stop_is_ignored(self):
        self.complete('a')
        self.clock.sleep(.1)
        self.complete('b')
        self.event('Stop','a')
        self.assertEqual(len(self.query('SELECT * FROM comets')),2)
        _, first = self.prepare()
        self.assertEqual(self.query('SELECT session FROM comets WHERE started IS NOT NULL'), [('a',)])
        self.clock.sleep(2)
        _, second = self.prepare()
        self.assertEqual(self.query('SELECT session FROM comets WHERE started IS NOT NULL'), [('b',)])
        self.assertNotEqual(first['source'],second['source'])

    def test_read_queued_task_is_skipped(self):
        self.complete('a'); self.complete('b')
        self.prepare()
        self.unread.remove('b')
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("UPDATE receipts SET observed=1")
            b.reconcile_read_state(db,self.unread,self.clock.now())
        self.clock.sleep(2)
        _, comet = self.prepare()
        self.assertIsNone(comet)
        self.assertEqual(self.query('SELECT * FROM comets'),[])

    def test_read_during_comet_finishes_before_scene_returns(self):
        self.complete()
        self.run_worker([(1000.5,lambda:self.unread.clear())])
        selections = [c for c in self.device.calls if c[1]=='PUT' and c[2]=='/effects' and 'select' in c[3]]
        self.assertEqual(selections[-1][3]['select'],'Beach Waves')
        self.assertGreaterEqual(selections[-1][0],1002)
        self.assertEqual(self.query('SELECT * FROM comets'),[])

    def test_read_active_source_is_reserved_until_finish(self):
        self.complete('a')
        for i in range(14): self.event('UserPromptSubmit',str(i))
        _, comet = self.prepare()
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("UPDATE receipts SET observed=1")
            b.reconcile_read_state(db,set(),1000.5)
        self.event('UserPromptSubmit','extra')
        self.prepare()
        self.assertEqual(self.query("SELECT slot FROM slots WHERE session='extra'"),[])
        self.clock.sleep(2)
        self.prepare()
        self.assertEqual(self.query("SELECT slot FROM slots WHERE session='extra'"),[(comet['source'],)])

    def test_completion_without_slot_waits_for_assignment(self):
        for i in range(15): self.event('UserPromptSubmit',str(i))
        self.prepare()
        self.complete('extra')
        _, comet = self.prepare()
        self.assertIsNone(comet)
        self.event('Interrupt','0')
        _, comet = self.prepare()
        self.assertIsNotNone(comet)

    def test_new_turn_and_interrupt_cancel_active_comet(self):
        for action in ('UserPromptSubmit','Interrupt'):
            self.complete()
            self.prepare()
            with contextlib.closing(database.connect_state(self.directory)) as db, db:
                b.transition(db,{'hook_event_name':action,'session_id':'a','turn_id':'2' if action=='UserPromptSubmit' else '1'},1000.5)
            self.assertEqual(self.query('SELECT * FROM comets'),[])
            self.event('SessionEnd')

    def test_free_quiet_clear_queue_and_do_not_accumulate(self):
        for mode in ('free','quiet'):
            self.mode('work')
            self.complete('a'); self.complete('b')
            self.prepare()
            self.mode(mode)
            self.assertEqual(self.query('SELECT * FROM comets'),[])
            self.complete('c')
            self.assertEqual(self.query('SELECT * FROM comets'),[])
            self.mode('work')
            self.assertIsNone(self.prepare()[1])

    def test_start_time_survives_failed_send_and_restart(self):
        self.complete()
        self.device.fail = lambda method,ep,payload: method=='PUT' and ep=='/effects'
        with self.assertRaises(OSError): self.run_worker()
        self.assertEqual(self.query('SELECT started FROM comets'),[(1000,)])
        self.clock.sleep(.5)
        seen=[]
        real=self.device.request
        def capture(cfg,*args,**kwargs):
            if cfg.get('_comet'): seen.append(copy.deepcopy(cfg['_comet']))
            return real(cfg,*args,**kwargs)
        from unittest.mock import patch
        with patch.object(self.device,'request',capture):
            self.run_worker([(1003,lambda:self.unread.clear())])
        self.assertTrue(seen)
        self.assertTrue(all(c['started']==1000 for c in seen))

    def test_expired_comet_not_replayed_after_restart(self):
        self.complete(); self.prepare(); self.clock.sleep(3)
        self.assertIsNone(self.prepare()[1])
        self.event('Stop')
        self.assertEqual(self.query('SELECT * FROM comets'),[])

    def test_historical_unread_reconciliation_does_not_enqueue(self):
        self.event('UserPromptSubmit')
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("UPDATE sessions SET status='ended'")
            b.reconcile_read_state(db,{'a'},self.clock.now())
        self.assertEqual(self.query('SELECT * FROM comets'),[])

    def test_preview_uses_no_fake_tasks_and_is_finite(self):
        sent=[]
        b.play_preview(self.config,'comet',lambda cfg,snap,t,loop:sent.append((cfg,snap,loop)),self.clock.sleep,self.clock.now)
        self.assertEqual(len(sent),1)
        self.assertFalse(any(sent[0][1]))
        self.assertEqual(sent[0][0]['_comet']['source'],7)
        self.assertFalse(sent[0][2])
        self.assertEqual(self.clock.now(),1002)

    def test_queued_comets_play_sequentially_in_worker(self):
        self.complete('a'); self.complete('b')
        starts=[]
        real=self.device.request
        def capture(cfg,*args,**kwargs):
            if cfg.get('_comet') and cfg['_comet'] not in starts: starts.append(copy.deepcopy(cfg['_comet']))
            return real(cfg,*args,**kwargs)
        from unittest.mock import patch
        with patch.object(self.device,'request',capture):
            self.run_worker([(1005,lambda:self.unread.clear())])
        self.assertEqual(len(starts),2)
        self.assertGreaterEqual(starts[1]['started']-starts[0]['started'],2)

    def test_switch_to_free_interrupts_active_comet_and_discards_queue(self):
        self.complete('a'); self.complete('b')
        self.run_worker([(1000.5,lambda:self.mode('free')),
                         (1001,lambda:self.unread.clear())])
        self.assertEqual(self.query('SELECT * FROM comets'),[])
        self.assertEqual(self.device.selected,'Beach Waves')
        writes=[c for c in self.device.calls if c[1]=='PUT']
        self.assertTrue(all(c[0] < 1001 for c in writes))

    def test_scene_end_after_read_keeps_active_source_until_finish(self):
        self.complete(); self.prepare()
        with contextlib.closing(database.connect_state(self.directory)) as db, db:
            db.execute("UPDATE receipts SET observed=1")
            b.reconcile_read_state(db,set(),1000.5)
        self.event('SessionEnd')
        self.assertIsNotNone(self.prepare()[1])
        self.clock.sleep(2)
        self.assertIsNone(self.prepare()[1])
