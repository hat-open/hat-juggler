from pathlib import Path

from hat.doit import common
from hat.doit.docs import (build_sphinx,
                           build_pdoc)
from hat.doit.js import (get_task_build_npm,
                         ESLintConf,
                         run_eslint)
from hat.doit.py import (get_task_build_wheel,
                         get_task_run_pytest,
                         get_task_create_pip_requirements,
                         run_flake8)


__all__ = ['task_clean_all',
           'task_node_modules',
           'task_build',
           'task_build_py',
           'task_build_js',
           'task_build_ts',
           'task_check',
           'task_test',
           'task_docs',
           'task_pip_requirements']


build_dir = Path('build')
docs_dir = Path('docs')
src_py_dir = Path('src_py')
src_js_dir = Path('src_js')
pytest_dir = Path('test_pytest')

build_docs_dir = build_dir / 'docs'
build_py_dir = build_dir / 'py'
build_js_dir = build_dir / 'js'
build_ts_dir = build_dir / 'ts'


def task_clean_all():
    """Clean all"""
    return {'actions': [(common.rm_rf, [build_dir])]}


def task_node_modules():
    """Install node_modules"""
    return {'actions': ['npm install --silent --progress false']}


def task_build():
    """Build"""
    return {'actions': None,
            'task_dep': ['build_py',
                         'build_js']}


def task_build_py():
    """Build Python wheel"""
    return get_task_build_wheel(src_dir=src_py_dir,
                                build_dir=build_py_dir)


def task_build_js():
    """Build JavaScript npm"""
    return get_task_build_npm(src_dir=build_ts_dir,
                              build_dir=build_js_dir,
                              name='@hat-open/juggler',
                              task_dep=['build_ts',
                                        'node_modules'])


def task_build_ts():
    """Build TypeScript"""
    return {'actions': ['npx tsc'],
            'task_dep': ['node_modules']}


def task_check():
    """Check"""
    return {'actions': [(run_flake8, [src_py_dir]),
                        (run_flake8, [pytest_dir]),
                        (run_eslint, [src_js_dir, ESLintConf.TS])],
            'task_dep': ['node_modules']}


def task_test():
    """Test"""
    return get_task_run_pytest()


def task_docs():
    """Docs"""

    def build():
        build_sphinx(src_dir=docs_dir,
                     dst_dir=build_docs_dir,
                     project='hat-juggler')
        build_pdoc(module='hat.juggler',
                   dst_dir=build_docs_dir / 'py_api')

    return {'actions': [build]}


def task_pip_requirements():
    """Create pip requirements"""
    return get_task_create_pip_requirements()
