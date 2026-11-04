import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/sakurai-game-design/scripts'))
import search
from evidence import EvidenceStore


class SpecificMechanicBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = EvidenceStore(ROOT / 'knowledge', ROOT)
        cls.annotations = json.loads((ROOT / 'knowledge/annotations.json').read_text())['items']
        cls.techniques = {r['id']:r for r in search.load('techniques')}

    def scope(self, iid, query, context):
        return search.evaluate_scope(self.techniques[iid], self.annotations[iid], query, context)

    def test_single_hit_does_not_establish_multihit_scope(self):
        result = self.scope('FEEL-T15', 'hits feel weak', {'genre':'action', 'mechanics':['combat','sword','impact']})
        self.assertEqual(result['status'], 'needs_context')
        self.assertFalse(result['mandatory_change'])

    def test_explicit_multi_hit_can_establish_scope(self):
        result = self.scope('FEEL-T15', 'reliable attack sequence', {'genre':'platform fighter','mechanics':['combat','multi-hit','knockback']})
        self.assertEqual(result['status'], 'applicable')

    def test_no_combat_blocks_multihit_recipe(self):
        result = self.scope('FEEL-T15', 'reliable sequence', {'mechanics':['gardening'],'excluded_mechanics':['combat']})
        self.assertEqual(result['status'], 'not_applicable')

    def test_combat_alone_does_not_establish_launch_parameter_scope(self):
        result = self.scope('FEEL-T14', 'attack damage', {'genre':'action','mechanics':['combat']})
        self.assertEqual(result['status'], 'needs_context')

    def test_platform_fighter_establishes_launch_scope(self):
        result = self.scope('FEEL-T14', 'attack tuning', {'genre':'platform fighter','mechanics':['combat','knockback']})
        self.assertEqual(result['status'], 'applicable')


if __name__ == '__main__':
    unittest.main()
