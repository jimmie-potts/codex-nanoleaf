"""Private, source-only named animation favorites (#154)."""
import contextlib
import copy
import json
import unittest
from unittest.mock import patch

import test_controller_animations as animations
import database
import effects
import integration_api


class FavoriteTest(animations.AnimationTest):
    def edit(self, command):
        req, result = self.play(command)
        self.assertEqual(result[0], 202, result)
        with contextlib.closing(database.connect_state(self.directory)) as db:
            with db:
                integration_api.process(db, self.config, now=self.clock.now())
        receipt = self.receipt(req)
        self.assertEqual((receipt['outcome'], receipt['priorEffects']), ('applied', 'configuration'), receipt)
        self.assertEqual(receipt['physicalOutcome'], 'unknown')
        return req

    def save(self, name='my ripple', recipe=None):
        return self.edit({'kind': 'animation.save', 'name': name,
                          'animation': recipe or {'pattern': 'wave', 'colors': ['#123456']}})

    def test_save_freezes_recipe_survives_reopen_and_replays(self):
        self.free()
        req = self.save()
        expected = {'pattern': 'wave', 'colors': ['#123456'], 'speed': 'medium', 'direction': 'right', 'loop': True}
        with contextlib.closing(database.connect_state(self.directory)):
            pass
        self.assertEqual(self.options()['favorites'], [{'name': 'my ripple', 'animation': expected}])
        self.assertEqual(self.puts(), [])
        self.assertEqual(self.app.integration_admit(self.token, req)[0], 200)
        play, result = self.play({'kind': 'animation.play', 'favorite': 'my ripple'})
        self.assertEqual(result[0], 202, result)
        self.run_worker()
        self.assertEqual(self.receipt(play)['outcome'], 'sent')
        self.assertEqual(self.puts(), [('/effects', effects.render(dict(kind='animation.play', **expected), self.config['line_groups'], self.config['line_positions']))])

    def test_collision_atomic_rename_delete_bound_and_name_identity(self):
        self.save('ripple')
        self.save('Ripple', {'preset': 'cozy'})
        before = self.options()
        for command in [
            {'kind': 'animation.save', 'name': 'ripple', 'animation': {'preset': 'ocean'}},
            {'kind': 'animation.rename', 'name': 'ripple', 'newName': 'Ripple'},
            {'kind': 'animation.rename', 'name': 'ripple', 'newName': 'ripple'},
        ]:
            self.assertEqual(self.play(command)[1], (409, {'failure': {'code': 'revision-conflict'}}))
            self.assertEqual(self.options(), before)
        self.edit({'kind': 'animation.rename', 'name': 'ripple', 'newName': 'renamed'})
        self.assertEqual([item['name'] for item in self.options()['favorites']], ['Ripple', 'renamed'])
        self.edit({'kind': 'animation.forget', 'name': 'renamed'})
        for kind in ('animation.forget', 'animation.rename'):
            command = {'kind': kind, 'name': 'missing'}
            if kind == 'animation.rename': command['newName'] = 'available'
            self.assertEqual(self.play(command)[1], (422, {'failure': {'code': 'unsupported-capability'}}))
        for n in range(31): self.save(str(n))
        before = self.options()
        self.assertEqual(self.play({'kind': 'animation.save', 'name': 'overflow', 'animation': {'preset': 'cozy'}})[1],
                         (429, {'failure': {'code': 'capacity'}}))
        self.assertEqual(self.options(), before)
        self.edit({'kind': 'animation.rename', 'name': '0', 'newName': 'at capacity'})
        self.assertEqual(len(self.options()['favorites']), 32)
        self.edit({'kind': 'animation.forget', 'name': 'at capacity'})
        self.save(' replacement ')
        self.assertIn(' replacement ', [item['name'] for item in self.options()['favorites']])

    def test_preset_defaults_are_frozen_without_snapshot_or_display_mutation(self):
        for mode in ('work', 'quiet', 'free'):
            self.mode(mode)
            before = self.app.integration_snapshot(self.token, 'device')
            wakeup = self.query("SELECT value FROM meta WHERE key='event_revision'")
            self.save(mode, {'preset': 'cozy'})
            after = self.app.integration_snapshot(self.token, 'device')
            self.assertEqual(set(after), set(before))
            self.assertEqual(after['capabilities'], before['capabilities'])
            self.assertEqual(after['limits'], before['limits'])
            self.assertEqual(after['mode'], mode.capitalize())
            self.assertNotEqual(after['revision'], before['revision'])
            self.assertEqual(self.query("SELECT value FROM meta WHERE key='event_revision'"), wakeup)
        self.assertEqual(self.device.calls, [])
        saved = copy.deepcopy(self.options()['favorites'])
        with patch.dict(effects.PRESETS, cozy={'pattern': 'pulse', 'colors': ['#ffffff']}), patch.dict(effects.DEFAULTS, loop=False):
            self.assertEqual(self.options()['favorites'], saved)
        self.assertEqual(saved[0]['animation'], dict(effects.PRESETS['cozy'], loop=True))
        reader = animations.server.issue(self.directory, 'hub-reader', ['read'])
        before_bytes = (self.directory / 'status.sqlite').read_bytes()
        options = self.app.integration_animations(reader, 'device')
        hub_snapshot = self.app.integration_snapshot(reader, 'device')
        self.assertEqual((self.directory / 'status.sqlite').read_bytes(), before_bytes)
        self.assertNotIn('favorites', hub_snapshot)
        self.assertNotIn('cozy', json.dumps(hub_snapshot))
        self.assertEqual((options['limits']['maxFavorites'], options['limits']['maxFavoriteName']), (32, 80))

    def test_malformed_names_recipes_mixed_selectors_and_bounds_are_rejected(self):
        before = self.options()['nextRequestId']
        for name in ('', ' ', '\n', 'a\x00b', 'x' * 81, 'a\u200bb', 17):
            for command in ({'kind': 'animation.save', 'name': name, 'animation': {'preset': 'cozy'}},
                            {'kind': 'animation.rename', 'name': 'old', 'newName': name},
                            {'kind': 'animation.forget', 'name': name}):
                self.assertEqual(self.play(command)[1][0], 400, command)
        for recipe in ({}, {'favorite': 'other'}, {'kind': 'animation.play', 'preset': 'cozy'},
                       {'preset': 'cozy', 'speed': 'fast'}, {'preset': 'absent'},
                       {'pattern': 'pulse', 'colors': ['#ffffff'], 'direction': 'clockwise'}):
            self.assertEqual(self.play({'kind': 'animation.save', 'name': 'bad', 'animation': recipe})[1][0], 400)
        self.assertEqual(self.options()['nextRequestId'], before)
        self.save('😀' * 80)
        self.free()
        self.save('bounded')
        for extra in ({'preset': 'cozy'}, {'pattern': 'wave'}, {'loop': False}):
            self.assertEqual(self.play(dict(kind='animation.play', favorite='bounded', **extra))[1][0], 400)
        self.assertEqual(self.play({'kind': 'animation.play', 'favorite': 'absent'})[1][0], 422)
        before = self.options()
        with patch.object(effects, 'MAX_BYTES', 100):
            self.assertEqual(self.play({'kind': 'animation.play', 'favorite': 'bounded'})[1][0], 429)
        self.assertEqual(self.options(), before)
        for mode in ('work', 'quiet'):
            self.mode(mode)
            self.assertEqual(self.play({'kind': 'animation.play', 'favorite': 'bounded'})[1][0], 422)

    def test_stale_authority_replay_cancel_expiry_and_hold(self):
        self.free()
        reader = animations.server.issue(self.directory, 'read-only', ['read'])
        command = {'kind': 'animation.save', 'name': 'queued', 'animation': {'preset': 'ocean'}}
        request = self.request(command)
        self.assertEqual(self.app.integration_admit(reader, request)[0], 403)
        self.assertEqual(self.play(command, expectedRevision='f' * 64)[1][0], 409)
        req, result = self.play(command)
        self.assertEqual(result[0], 202)
        self.assertEqual(self.app.integration_admit(self.token, req), result)
        self.assertEqual(self.app.integration_admit(self.token, dict(req, command=dict(command, name='other')))[0], 409)
        self.assertEqual(self.play(dict(command, name='next'))[1][0], 429)
        with contextlib.closing(database.connect_state(self.directory)) as db:
            with db:
                integration_api.hold(db)
                integration_api.process(db, self.config, now=self.clock.now())
                self.assertTrue(animations.server.state.held(db, animations.b.control_state(db)['revision']))
        self.assertEqual(self.receipt(req)['outcome'], 'applied')
        self.assertEqual(self.device.calls, [])
        req, _ = self.play(dict(command, name='cancelled'))
        self.assertEqual(self.app.integration_cancel(self.token, 'device', req['requestId'])[1]['outcome'], 'cancelled')
        req, _ = self.play(dict(command, name='expired'))
        with contextlib.closing(database.connect_state(self.directory)) as db:
            with db: integration_api.process(db, self.config, now=self.clock.now() + 31)
        self.assertEqual(self.receipt(req)['failure']['code'], 'request-expired')
        self.assertEqual([item['name'] for item in self.options()['favorites']], ['queued'])

    def test_worker_applies_save_without_light_write_and_rejects_changed_revision(self):
        self.free()
        request, result = self.play({'kind': 'animation.save', 'name': 'worker', 'animation': {'preset': 'forest'}})
        self.assertEqual(result[0], 202)
        self.run_worker()
        self.assertEqual(self.receipt(request)['outcome'], 'applied')
        self.assertEqual(self.puts(), [])
        request, result = self.play({'kind': 'animation.rename', 'name': 'worker', 'newName': 'stale'})
        self.mode('free')
        self.run_worker()
        self.assertEqual(self.receipt(request)['failure']['code'], 'revision-conflict')
        self.assertEqual([item['name'] for item in self.options()['favorites']], ['worker'])

    def test_revocation_and_wrong_target_never_save_or_play(self):
        self.free()
        command = {'kind': 'animation.save', 'name': 'revoked', 'animation': {'preset': 'cozy'}}
        before = self.options()['nextRequestId']
        self.assertEqual(self.play(command, deviceId='unknown')[1][0], 403)
        self.assertEqual(self.options()['nextRequestId'], before)
        request, result = self.play(command)
        self.assertEqual(result[0], 202)
        with contextlib.closing(database.connect_state(self.directory)) as db:
            with db:
                db.execute("UPDATE controller_credentials SET active=0 WHERE principal='client'")
                integration_api.process(db, self.config, now=self.clock.now())
        self.assertEqual(self.receipt(request)['failure']['code'], 'forbidden')
        self.assertEqual(self.query('SELECT name FROM animation_favorites'), [])
        self.assertEqual(self.puts(), [])
