from pathlib import Path
import subprocess
import sys

from hat.doit import common

# from .js import src_js_dir


__all__ = ['task_docs',
           'task_docs_py',
           'task_docs_js']


build_dir = Path('build/docs')
docs_dir = Path('docs')
py_api_dir = build_dir / 'py_api'
js_api_dir = build_dir / 'js_api'


def task_docs():
    """Docs - build documentation"""
    return {'actions': [(common.sphinx_build, [
                            common.SphinxOutputType.HTML,
                            docs_dir,
                            build_dir])],
            'task_dep': ['docs_py',
                         'docs_js']}


def task_docs_py():
    """Docs - build python documentation"""

    def build():
        common.mkdir_p(py_api_dir.parent)
        subprocess.run([sys.executable, '-m', 'pdoc',
                        '--html', '--skip-errors', '-f',
                        '-o', str(py_api_dir),
                        'hat.juggler'],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=True)

    return {'actions': [build]}


def task_docs_js():
    """Docs - build javascript documentation"""

    def build():
        pass
        # common.mkdir_p(js_api_dir.parent)
        # with tempfile.TemporaryDirectory() as tmpdir:
        #     tmpdir = Path(tmpdir)
        #     conf_path = tmpdir / 'jsdoc.json'
        #     conf_path.write_text(json.encode({
        #         "source": {
        #             "include": str(src_js_dir)
        #         },
        #         "plugins": [
        #             "plugins/markdown"
        #         ],
        #         "opts": {
        #             "template": "node_modules/docdash",
        #             "destination": str(js_api_dir),
        #             "recurse": True
        #         },
        #         "templates": {
        #             "cleverLinks": True
        #         }
        #     }))
        #     js_doc_path = Path('node_modules/.bin/jsdoc')
        #     subprocess.run([str(js_doc_path), '-c', str(conf_path)],
        #                    check=True)

    return {'actions': [build],
            'task_dep': ['js_deps']}
