import ast
import html
import json
import re
import tempfile
import types
import unittest
from pathlib import Path

SOURCE = Path('main.py').read_text()

def load_fn(name, env):
    tree = ast.parse(SOURCE)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), env)
    return env[name]

class Regressions(unittest.TestCase):
    def test_render_preserves_rows_and_assets(self):
        fn = load_fn('render_paper_list_html_from_json', {'html_lib': html, 'json': json})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'papers.json'
            p.write_text(json.dumps([{'date': '2026-10-27', 'title': '<script>x</script>', 'arxiv_id': '2610.1', 'authors': [], 'summary': 'safe', 'pdf_url': ''}]))
            text = fn(str(p))
        self.assertIn('&lt;script&gt;', text)
        self.assertIn('assets/date-index.js', text)
        self.assertIn('assets/date-index.css', text)
        self.assertIn('2026-10-27', text)

    def test_default_ref_and_concurrency_guard(self):
        text = Path('.github/workflows/main.yml').read_text()
        self.assertNotIn('${{ vars.REF }}', text)
        self.assertIn('vars.REF || github.event.repository.default_branch', text)
        self.assertIn('Branch changed while collecting', text)
        self.assertNotIn('--force', text)

    def test_atom_entry_parsing_and_rate_limit_avoidance(self):
        class Author:
            def __init__(self, name): self.name = name
        class Link:
            def __init__(self, href, **kw): self.href = href; self.kw = kw
        class Result:
            def __init__(self, **kw): self.__dict__.update(kw)
            def get_short_id(self): return self.entry_id.split('arxiv.org/abs/')[-1]
        Result.Author = Author
        Result.Link = Link
        class DummyPaper:
            def __init__(self, res):
                self._paper = res
                self.arxiv_id = re.sub(r'v\d+$', '', res.get_short_id())
        class DummyBar:
            def __init__(self, **kw): self.count = 0
            def update(self, n): self.count += n
            def close(self): pass
        env = {
            're': re,
            'arxiv': types.SimpleNamespace(Result=Result),
            'ArxivPaper': DummyPaper,
            'tqdm': lambda **kw: DummyBar(**kw),
            'logger': types.SimpleNamespace(debug=lambda *a, **k: None),
        }
        to_result = load_fn('_result_from_atom_entry', env)
        entry = types.SimpleNamespace(
            id='oai:arXiv.org:2610.35905v1',
            title='Task-Utility\n  IQA',
            summary='arXiv:2610.35905v1 Announce Type: new \nAbstract: Clean abstract text.',
            arxiv_announce_type='new',
            get=lambda k, default=None: [{'name': 'Alice Smith, Bob Jones'}] if k == 'authors' else default,
        )
        res = to_result(entry)
        self.assertEqual(res.get_short_id(), '2610.35905v1')
        self.assertEqual(res.title, 'Task-Utility IQA')
        self.assertEqual(res.summary, 'Clean abstract text.')
        self.assertEqual([a.name for a in res.authors], ['Alice Smith', 'Bob Jones'])
        self.assertEqual(res.links[1].href, 'https://arxiv.org/pdf/2610.35905.pdf')

        dup_entry = types.SimpleNamespace(
            id='oai:arXiv.org:2610.35905v1',
            title='Task-Utility IQA',
            summary='arXiv:2610.35905v1 Announce Type: new \nAbstract: Clean abstract text.',
            arxiv_announce_type='new',
            get=entry.get,
        )
        replace_entry = types.SimpleNamespace(
            id='oai:arXiv.org:2610.99999v2',
            title='Replaced Paper',
            summary='arXiv:2610.99999v2 Announce Type: replace \nAbstract: Ignored.',
            arxiv_announce_type='replace',
            get=entry.get,
        )
        env['_fetch_atom_feed'] = lambda q: types.SimpleNamespace(
            feed={'title': 'cs.CV updates on arXiv.org'},
            entries=[entry, dup_entry, replace_entry],
        )
        get_papers = load_fn('get_arxiv_paper', env)
        papers = get_papers('cs.CV', debug=False)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].arxiv_id, '2610.35905')

        env['_fetch_atom_feed'] = lambda q: types.SimpleNamespace(
            feed={'title': 'Feed error for query: bad'},
            entries=[],
        )
        with self.assertRaises(Exception):
            get_papers('bad', debug=False)

if __name__ == '__main__': unittest.main()
