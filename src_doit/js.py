from pathlib import Path
import json
import subprocess

from hat.doit import common


__all__ = ['task_js_build',
           'task_js_check',
           'task_js_deps',
           'task_js_deps_clean']


build_dir = Path('build/js')
src_js_dir = Path('src_js')
node_modules_dir = Path('node_modules')
readme_path = Path('README.rst')


def task_js_build():
    """JavaScript - build"""

    def mappings():
        yield (src_js_dir / '@hat-open/juggler.js',
               build_dir / 'index.js')

    def build():
        common.rm_rf(build_dir)
        common.mkdir_p(build_dir)

        dst_readme_path = build_dir / readme_path.with_suffix('.md').name
        subprocess.run(['pandoc', str(readme_path),
                        '-o', str(dst_readme_path)],
                       check=True)

        for src_path, dst_path in mappings():
            common.mkdir_p(dst_path.parent)
            common.cp_r(src_path, dst_path)

        (build_dir / 'package.json').write_text(json.dumps({
            'name': '@hat-open/juggler',
            'version': common.get_version(common.VersionType.SEMVER),
            'description': 'Hat juggler protocol',
            'homepage': 'https://github.com/hat-open/hat-juggler',
            'bugs': 'https://github.com/hat-open/hat-juggler/issues',
            'license': common.License.APACHE2.value,
            'main': 'index.js',
            'repository': 'hat-open/hat-juggler',
            'dependencies': {'jiff': '*',
                             '@hat-open/util': '*'}
        }, indent=4))

        subprocess.run(['npm', 'pack', '--silent'],
                       stdout=subprocess.DEVNULL,
                       cwd=str(build_dir),
                       check=True)

    return {'actions': [build],
            'task_dep': ['js_deps']}


def task_js_check():
    """JavaScript - check with eslint"""
    eslint_path = node_modules_dir / '.bin/eslint'
    return {'actions': [f'{eslint_path} {src_js_dir}'],
            'task_dep': ['js_deps']}


def task_js_deps():
    """JavaScript - install dependencies"""
    return {'actions': ['yarn install --silent']}


def task_js_deps_clean():
    """JavaScript - remove dependencies"""
    return {'actions': [(common.rm_rf, [node_modules_dir,
                                        Path('yarn.lock')])]}
