import json
import tempfile
import unittest
from pathlib import Path
from smartbins.core import System, UNCONFIRMED


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name)/'test.db')
        self.s = System(self.path)

    def tearDown(self):
        self.s.db.close()
        self.tmp.cleanup()

    def test_A_withdrawal(self):
        p = self.s.scenario('A')
        self.assertEqual(p['current_weight']-50,190)
        self.assertEqual(self.s.material('MAT-0001')['stock'],95)
        e = self.s.events()[0]
        self.assertEqual((e['kind'],e['quantity'],e['employee']),('SAÍDA',5,'João'))
        self.assertTrue(e['document'].startswith('SIM-'))
        self.assertNotIn('quantity',p)
        self.assertNotIn('units',p)

    def test_B_small_part(self):
        p = self.s.scenario('B')
        self.assertAlmostEqual(p['current_weight']-50,22)
        self.assertEqual(self.s.material('MAT-0002')['stock'],220)
        self.assertEqual(self.s.events()[0]['quantity'],20)

    def test_C_invalid_mass(self):
        self.s.scenario('C')
        self.assertEqual(self.s.material('MAT-0001')['stock'],100)
        self.assertEqual(self.s.events()[0]['status'],'PENDENTE VALIDAÇÃO')
        self.assertIsNone(self.s.events()[0]['document'])

    def test_D_recovery_persistent_and_idempotent(self):
        p = self.s.scenario('D')
        self.assertEqual(self.s.material('MAT-0001')['stock'],100)
        self.assertEqual(self.s.events()[0]['status'],'PENDENTE SAP')
        self.s.db.close()
        self.s = System(self.path)
        self.s.set_online(True)
        self.s.retry()
        doc = self.s.events()[0]['document']
        self.s.retry()
        self.s.receive(p)
        self.assertEqual(len(self.s.events()),1)
        self.assertEqual(self.s.events()[0]['document'],doc)
        self.assertEqual(self.s.material('MAT-0001')['stock'],95)

    def test_E_ambiguous_identity(self):
        self.s.scenario('E')
        self.assertEqual(self.s.material('MAT-0001')['stock'],95)
        self.assertEqual(self.s.events()[0]['employee'],UNCONFIRMED)
        self.assertEqual(self.s.events()[0]['status'],'REGISTRADO')

    def test_instability_then_new_stable_reading(self):
        self.s.simulate('MAT-0001',-5,unstable=True)
        self.assertEqual(self.s.material('MAT-0001')['stock'],100)
        self.s.simulate('MAT-0001')
        self.assertEqual(self.s.material('MAT-0001')['stock'],95)

    def test_below_threshold(self):
        self.s.simulate('MAT-0001')
        self.assertEqual(self.s.events()[0]['status'],'IGNORADO')
        self.assertEqual(self.s.material('MAT-0001')['stock'],100)

    def test_negative_physical_stock_blocked(self):
        with self.assertRaises(ValueError):
            self.s.simulate('MAT-0001',-101)
        self.assertEqual(len(self.s.events()),0)

    def test_disconnection(self):
        self.s.set_connected('MAT-0001',False)
        with self.assertRaises(ValueError):
            self.s.simulate('MAT-0001',-1)

    def test_ordered_offline_queue(self):
        self.s.set_online(False)
        self.s.simulate('MAT-0001',-5)
        self.s.simulate('MAT-0001',-10)
        self.s.set_online(True)
        self.s.retry()
        self.assertEqual(self.s.material('MAT-0001')['stock'],85)
        self.assertEqual(len([e for e in self.s.events() if e['document']]),2)

    def test_offline_entry_before_large_withdrawal(self):
        self.s.set_online(False)
        self.s.simulate('MAT-0001',100)
        self.s.simulate('MAT-0001',-150)
        self.s.set_online(True)
        self.s.retry()
        self.assertEqual(self.s.material('MAT-0001')['stock'],50)
        self.assertTrue(all(e['status']=='REGISTRADO' for e in self.s.events()))

    def test_new_material(self):
        self.s.add_material('MAT-0003','Peça real','CX-003','S3','Zona C',3.,10,20.,2,.1,.2)
        self.s.simulate('MAT-0003',-1)
        self.assertEqual(self.s.material('MAT-0003')['stock'],9)

    def test_minimum_alert_balance(self):
        self.s.simulate('MAT-0001',-90)
        m = self.s.material('MAT-0001')
        self.assertLess(m['stock'],m['minimum'])

    def test_edit_recalibrates_only_before_events(self):
        self.s.save_material('MAT-0001',{'unit_weight':3.,'initial_qty':10})
        self.assertEqual(self.s.material('MAT-0001')['physical'],80.)
        self.s.simulate('MAT-0001',-1)
        with self.assertRaises(ValueError):
            self.s.save_material('MAT-0001',{'unit_weight':4.})


if __name__=='__main__':
    unittest.main()
