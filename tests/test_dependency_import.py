"""Regressão: Altair deve importar antes da inicialização do Streamlit."""
import subprocess
import sys
import unittest
from pathlib import Path


class DependencyImportTests(unittest.TestCase):
    def test_altair_import_and_schema_in_fresh_python(self):
        # Um processo novo impede que imports já em cache escondam a falha TypedDict.
        result = subprocess.run(
            [sys.executable, '-c',
             'import altair as alt; '
             'chart = alt.Chart(alt.Data(values=[{"x": 1, "y": 2}])).mark_bar()'
             '.encode(x="x:Q", y="y:Q"); '
             'chart.to_dict(validate=True); '
             'from smartbins.presentation import bars, readings_chart; '
             'print("Altair importado e schema validado:", alt.__version__)'],
            cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('Altair importado e schema validado:',result.stdout)


if __name__=='__main__':
    unittest.main()
