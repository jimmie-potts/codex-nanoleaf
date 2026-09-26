"""The measurement harness uses the real owners and authenticated loopback feed."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('measure_shared', ROOT / 'scripts/measure-shared.py')
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class SharedMeasurementTest(unittest.TestCase):
    def test_reduced_measurement_preserves_profiles_and_receipt(self):
        # Fail before any device or personal hook access, while exercising the real
        # fetch, validation, SQLite projection, allocation and effect construction.
        with patch('transport.light_request', side_effect=AssertionError('device access')), \
                patch('codex_hooks.has_legacy_hooks', side_effect=AssertionError('Codex hook access')):
            receipt = measure.run(samples=1)
        self.assertEqual(receipt['schemaVersion'], 1)
        self.assertEqual(receipt['samplesPerRepetition'], 1)
        self.assertEqual([profile['sessions'] for profile in receipt['profiles']], [1, 10, 50])
        self.assertEqual(receipt['bounds'], {'pollIntervalSeconds': 1, 'transportDeadlineSeconds': 2.5,
                                           'responseBytes': 16 * 1024 * 1024, 'concurrentRequestsPerWorker': 1})
        self.assertEqual(len(receipt['limitations']), 2)
        for profile in receipt['profiles']:
            with self.subTest(sessions=profile['sessions']):
                self.assertEqual(profile['visibleCapacity'], 15)
                self.assertEqual(len(profile['repetitions']), 3)
                for repetition in profile['repetitions']:
                    self.assertEqual(repetition['samples'], 1)
                    self.assertEqual(set(repetition), {'samples', 'p50Ms', 'p95Ms', 'p99Ms', 'maximumMs', 'processCpuMs'})
                    self.assertGreaterEqual(repetition['p50Ms'], 0)
                    self.assertEqual(repetition['p50Ms'], repetition['maximumMs'])


if __name__ == '__main__':
    unittest.main()
