"""Exercita o script Streamlit em banco temporário, sem alterar a demonstração."""
import os
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1]/'app.py'


class InterfaceTests(unittest.TestCase):
    def test_pages_and_scenario(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                app = AppTest.from_file(str(APP)).run(timeout=30)
                self.assertEqual(list(app.exception),[])
                app.checkbox[1].check().run()
                next(b for b in app.button if b.label.startswith('Cenário A')).click().run()
                self.assertEqual(list(app.exception),[])
                from smartbins.core import System
                s = System()
                self.assertEqual(s.material('MAT-0001')['stock'],95)
                s.db.close()
                for page in ['Almoxarifado inteligente','Simulação ESP32','Integração SAP',
                             'Histórico de movimentações','Indicadores e acuracidade']:
                    app.sidebar.radio[0].set_value(page).run(timeout=30)
                    self.assertEqual(list(app.exception),[],page)
            finally:
                os.chdir(old)


if __name__=='__main__':
    unittest.main()
