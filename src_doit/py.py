from pathlib import Path

from hat.doit import common
from hat.doit.py import (build_wheel,
                         run_pytest,
                         run_flake8)


__all__ = ['task_py_build',
           'task_py_check',
           'task_py_test']


build_py_dir = Path('build/py')
src_py_dir = Path('src_py')
pytest_dir = Path('test_pytest')


def task_py_build():
    """Python - build"""

    def build():
        build_wheel(
            src_dir=src_py_dir,
            dst_dir=build_py_dir,
            name='hat-juggler',
            description='Hat Juggler protocol',
            url='https://github.com/hat-open/hat-juggler',
            license=common.License.APACHE2,
            packages=['hat'])

    return {'actions': [build]}


def task_py_check():
    """Python - check with flake8"""
    return {'actions': [(run_flake8, [src_py_dir]),
                        (run_flake8, [pytest_dir])]}


def task_py_test():
    """Python - test"""
    return {'actions': [lambda args: run_pytest(pytest_dir, *(args or []))],
            'pos_arg': 'args'}
