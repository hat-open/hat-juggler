from pathlib import Path
import subprocess
import sys

from hat.doit import common


__all__ = ['task_py_build',
           'task_py_check',
           'task_py_test']


build_dir = Path('build/py')
src_py_dir = Path('src_py')
pytest_dir = Path('test_pytest')


def task_py_build():
    """Python - build"""

    def build():
        common.wheel_build(
            src_dir=src_py_dir,
            dst_dir=build_dir,
            src_paths=list(common.path_rglob(src_py_dir,
                                             blacklist={'__pycache__'})),
            name='hat-juggler',
            description='Hat Juggler protocol',
            url='https://github.com/hat-open/hat-juggler',
            license=common.License.APACHE2,
            packages=['hat'])

    return {'actions': [build]}


def task_py_check():
    """Python - check with flake8"""
    return {'actions': [(_run_flake8, [src_py_dir]),
                        (_run_flake8, [pytest_dir])]}


def task_py_test():
    """Python - test"""

    def run(args):
        subprocess.run([sys.executable, '-m', 'pytest',
                        '-s', '-p', 'no:cacheprovider',
                        *(args or [])],
                       cwd=str(pytest_dir),
                       check=True)

    return {'actions': [run],
            'pos_arg': 'args'}


def _run_flake8(path):
    subprocess.run([sys.executable, '-m', 'flake8', str(path)],
                   check=True)
