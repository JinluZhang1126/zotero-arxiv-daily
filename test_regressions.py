import ast
import html
import json
import tempfile
import unittest
from pathlib import Path

class Regressions(unittest.TestCase):
    def test_render_preserves_rows_and_assets(self):
        tree=ast.parse(Path('main.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_paper_list_html_from_json')
        env={'html_lib':html,'json':json}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'main.py','exec'),env)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'papers.json'
            p.write_text(json.dumps([{'date':'2026-10-27','title':'<script>x</script>','arxiv_id':'2610.1','authors':[],'summary':'safe','pdf_url':''}]))
            text=env[node.name](str(p))
        self.assertIn('&lt;script&gt;',text)
        self.assertIn('assets/date-index.js',text)
        self.assertIn('assets/date-index.css',text)
        self.assertIn('2026-10-27',text)

    def test_default_ref_and_concurrency_guard(self):
        text=Path('.github/workflows/main.yml').read_text()
        self.assertNotIn('${{ vars.REF }}',text)
        self.assertIn('vars.REF || github.event.repository.default_branch',text)
        self.assertIn('Branch changed while collecting',text)
        self.assertNotIn('--force',text)

if __name__ == '__main__': unittest.main()
