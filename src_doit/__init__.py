from pathlib import Path

from hat.doit import common
from hat.doit.docs import (build_sphinx,
                           build_pdoc)
from hat.doit.js import (build_npm,
                         run_eslint)
from hat.doit.py import (build_wheel,
                         run_pytest,
                         run_flake8)


__all__ = ['task_clean_all',
           'task_node_modules',
           'task_build',
           'task_build_py',
           'task_build_js',
           'task_check',
           'task_test',
           'task_docs']


build_dir = Path('build')
docs_dir = Path('docs')
src_py_dir = Path('src_py')
src_js_dir = Path('src_js')
pytest_dir = Path('test_pytest')

build_docs_dir = build_dir / 'docs'
build_py_dir = build_dir / 'py'
build_js_dir = build_dir / 'js'


def task_clean_all():
    """Clean all"""
    return {'actions': [(common.rm_rf, [build_dir])]}


def task_node_modules():
    """Install node_modules"""
    return {'actions': ['yarn install --silent']}


def task_build():
    """Build"""
    return {'actions': None,
            'task_dep': ['build_py',
                         'build_js']}


def task_build_py():
    """Build Python wheel"""

    def build():
        build_wheel(
            src_dir=src_py_dir,
            dst_dir=build_py_dir,
            name='hat-juggler',
            description='Hat Juggler protocol',
            url='https://github.com/hat-open/hat-juggler',
            license=common.License.APACHE2)

    return {'actions': [build]}


def task_build_js():
    """Build JavaScript npm"""

    def build():
        build_npm(
            src_dir=src_js_dir,
            dst_dir=build_js_dir,
            name='@hat-open/juggler',
            description='Hat juggler protocol',
            license=common.License.APACHE2,
            homepage='https://github.com/hat-open/hat-juggler',
            repository='hat-open/hat-juggler')

    return {'actions': [build],
            'task_dep': ['node_modules']}


def task_check():
    """Check"""
    return {'actions': [(run_flake8, [src_py_dir]),
                        (run_flake8, [pytest_dir]),
                        (run_eslint, [src_js_dir])],
            'task_dep': ['node_modules']}


def task_test():
    """Test"""
    return {'actions': [lambda args: run_pytest(pytest_dir, *(args or []))],
            'pos_arg': 'args'}


def task_docs():
    """Docs"""

    def build():
        build_sphinx(src_dir=docs_dir,
                     dst_dir=build_docs_dir,
                     project='hat-juggler')
        build_pdoc(module='hat.juggler',
                   dst_dir=build_docs_dir / 'py_api')

    return {'actions': [build]}
