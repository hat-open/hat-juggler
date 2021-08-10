from pathlib import Path

from hat.doit import common
from hat.doit.docs import (SphinxOutputType,
                           build_sphinx,
                           build_pdoc)

from .js import *  # NOQA
from .py import *  # NOQA
from . import js
from . import py


__all__ = ['task_clean_all',
           'task_build',
           'task_check',
           'task_test',
           'task_docs',
           *js.__all__,
           *py.__all__]


build_dir = Path('build')
docs_dir = Path('docs')

build_docs_dir = build_dir / 'docs'


def task_clean_all():
    """Clean all"""
    return {'actions': [(common.rm_rf, [build_dir])]}


def task_build():
    """Build"""
    return {'actions': None,
            'task_dep': ['py_build',
                         'js_build']}


def task_check():
    """Check"""
    return {'actions': None,
            'task_dep': ['py_check',
                         'js_check']}


def task_test():
    """Test"""
    return {'actions': None,
            'task_dep': ['py_test']}


def task_docs():
    """Docs"""
    return {'actions': [(build_sphinx, [SphinxOutputType.HTML,
                                        docs_dir,
                                        build_docs_dir]),
                        (build_pdoc, ['hat.juggler',
                                      build_docs_dir / 'py_api'])]}
