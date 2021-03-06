#!/usr/bin/env python3
import argparse
import fnmatch
import functools
import glob
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from typing import Callable, Optional


class InvalidArgument(Exception):
    pass


@functools.total_ordering
class Version:
    def __init__(self, version: str):
        self.version = version
        self.components = tuple(self._parse(version))

    @classmethod
    def _parse(self, version: str):
        """
        >>> tuple(Version._parse('1.2'))
        ((1, ''), (2, ''))
        >>> tuple(Version._parse('1.2-rc'))
        ((1, ''), (2, '-rc'))
        >>> tuple(Version._parse('1.beta'))
        ((1, ''), (0, 'beta'))
        """
        components = version.split('.')
        for c in components:
            try:
                yield int(c), ''
            except ValueError:
                result = re.fullmatch(r'(\d*)(.*)', c)
                # 数値部分が存在しない場合、数値部分として扱う。
                integer = result.group(1) or '0'
                string = result.group(2)
                yield int(integer), string

    def __str__(self):
        return self.version

    def __lt__(self, other: 'Version') -> bool:
        """
        >>> Version('0.1') < Version('0.2')
        True
        >>> Version('0.9') < Version('0.10')
        True
        >>> Version('0.9') < Version('1.0')
        True
        """
        return self.components < other.components

    def __eq__(self, other: 'Version') -> bool:
        """
        >>> Version('1.2') == Version('01.02')
        True
        """
        return self.components == other.components


class MinVersionMatcher:
    def __init__(self, version: str):
        self.version = Version(version)

    def match(self, ver: Version) -> bool:
        """
        >>> MinVersionMatcher('1.0').match(Version('0.9'))
        False
        >>> MinVersionMatcher('1.0').match(Version('1.0'))
        True
        >>> MinVersionMatcher('1.0').match(Version('2.3'))
        True
        """
        return self.version <= ver


class MaxVersionMatcher:
    def __init__(self, version: str):
        self.version = Version(version)

    def match(self, ver: Version) -> bool:
        """
        >>> MaxVersionMatcher('1.0').match(Version('0.9'))
        True
        >>> MaxVersionMatcher('1.0').match(Version('1.0'))
        False
        >>> MaxVersionMatcher('1.0').match(Version('2.3'))
        False
        """
        return ver < self.version


class MultiVersionMatcher:
    def __init__(self, version_pattern: str):
        self._matcher = self._make_matcher(version_pattern)

    @classmethod
    def _make_matcher(cls, pattern: str) -> Callable[[Version], bool]:
        """
        >>> MultiVersionMatcher._make_matcher('1.x')('0.0.0')
        False
        >>> MultiVersionMatcher._make_matcher('1.x')('1.0')
        True
        >>> MultiVersionMatcher._make_matcher('1.x')('1.2.3')
        True
        >>> MultiVersionMatcher._make_matcher('1.x')('1.3-rc1')
        True
        """
        if ',' in pattern or '.' in pattern:
            patterns = [s.strip() for s in pattern.split(',')]
        else:
            patterns = [pattern.strip()]

        matchers = []
        for p in patterns:
            glob_pattern = p.replace('x', '?*')
            regexp = fnmatch.translate(glob_pattern)
            matcher = re.compile(regexp).fullmatch
            matchers.append(matcher)

        return lambda version: any(m(version) for m in matchers)

    def match(self, ver: Version) -> bool:
        return self._matcher(str(ver))


class NullVersionMatcher:
    def match(self, ver: Version) -> bool:
        return True


class ShellCommand:
    def __init__(self, cmd: str):
        self.cmd = cmd

    def run(self, py: Optional['PythonInterpreter'] = None):
        r""" Run the shell commands.

        >>> ShellCommand('echo OK').run()
        'OK\n'
        >>> ShellCommand('echo NG; false').run()
        Traceback (most recent call last):
        ...
        subprocess.CalledProcessError: Command 'echo NG; false' returned non-zero exit status 1.
        >>> ShellCommand('echo stderr >&2').run()
        'stderr\n'
        """
        new_env = {**os.environ}
        if py:
            new_env['PATH'] = py.bin_dir + ':' + new_env.get('PATH', '')
        result = subprocess.run(self.cmd, shell=True, check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=new_env,
                                encoding='utf8')
        return result.stdout


class NullShellCommand:
    def run(self):
        return ''


class PythonCommand:
    def __init__(self, args):
        self.args = args

    def run(self, py: 'PythonInterpreter'):
        new_env = {**os.environ}
        new_env['PATH'] = py.bin_dir + ':' + new_env.get('PATH', '')
        result = subprocess.run(['python', *self.args], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=new_env,
                                encoding='utf8')
        return result.stdout


@dataclass
class PythonInterpreter:
    binary_path: str
    bin_dir: str
    version: Version


class PythonRepository:
    def __init__(self, prefix):
        self.prefix = prefix

    def find(self, matcher: Callable[[Version], bool]):
        for py in self.find_all():
            if matcher(py.version):
                yield py

    def find_all(self):
        yield from self.find_all_cpython()
        # yield from self.find_all_pypy()

    def find_all_cpython(self):
        pattern = self.prefix + '/Python-*/bin/python'
        binaries = glob.glob(pattern)
        for bin in binaries:
            version_str = re.search(r'/Python-([^/]+)/', bin).group(1)
            yield PythonInterpreter(
                binary_path=bin,
                bin_dir=os.path.dirname(bin),
                version=Version(version_str),
            )

    def find_all_pypy(self):
        raise NotImplementedError()


class SectionPrinter:
    def __init__(self, suppress_empty_msg=True, file=None):
        self.suppress_empty_msg = suppress_empty_msg
        self.file = file
        self._need_section_gap = False

    def print(self, header: str, msg: str):
        if self.suppress_empty_msg and not msg:
            # msgが空なので、何も出力しない。
            return
        file = self.file
        end = None
        if msg.endswith('\n'):
            # msgが改行で終わっているときは、print()で改行を出力しないようにする。
            end = ''

        if self._need_section_gap:
            print()
        print(self._decorate_header(header), file=file)
        print(msg, end=end, file=file)
        self._need_section_gap = True

    def _decorate_header(self, header: str) -> str:
        return f'=====> {header} <====='


class CompactSectionPrinter:
    """
    >>> csp = CompactSectionPrinter()
    >>> csp.print('0.1', 'alpha')
    >>> csp.print('0.2', 'alpha')
    >>> csp.print('0.3', 'alpha')
    >>> csp.print('0.4', 'beta')
    =====> 0.1 ~ 0.3 <=====
    alpha
    >>> csp.print('1.0', 'stable')
    <BLANKLINE>
    =====> 0.4 <=====
    beta
    >>> csp.close()
    <BLANKLINE>
    =====> 1.0 <=====
    stable
    """

    def __init__(self, file=None):
        # 実行結果を出力するために使用するため、メッセージが空でも出力するようにする。
        self.p = SectionPrinter(suppress_empty_msg=False, file=file)
        self.first_header = None
        self.last_header = None
        self.previous_msg = None

    def _is_first(self) -> bool:
        return self.first_header is None

    def _is_omittable(self, msg: str) -> bool:
        return self.previous_msg == msg

    def _print(self):
        header = self.first_header
        if self.last_header:
            header = f'{self.first_header} ~ {self.last_header}'
        self.p.print(header, self.previous_msg)

    def _update_section(self, header: Optional[str], out: Optional[str]):
        if not self._is_first():
            self._print()

        self.first_header = header
        self.last_header = None
        self.previous_msg = out

    def print(self, header: str, msg: str, file=None):
        if self._is_first() or not self._is_omittable(msg):
            self._update_section(header, msg)
        else:
            self.last_header = header

    def close(self):
        self._update_section(None, None)


def parse_args():
    parser = argparse.ArgumentParser(
        prog='all-python',
        epilog=(textwrap.dedent(r'''
            Example:
              Show this message:
                $ all-python --help
              
              Run a python script on all python versions:
                $ all-python -- -c 'print(type(u""))'
                Note that "-c '...'" is the argument of python interpreter.
                
              Run a shell script:
                $ all-python -b 'echo before' \
                             -E 'python foo.py' \
                             -a 'echo after'
              
              Specify the python version:
                Specify the a version:
                $ all-python -v 3.7.3 -- -c 'print(type(u""))'
                
                Specify versions by pattern:
                $ all-python -v 2.7.x -- -c 'print(type(u""))'
                It will be execute on Python 2.7.1 ~ 2.7.16.
                
                Specify multiple patterns:
                $ all-python -v '2.7.x, 3.7.x' -- -c 'print(type(u""))'
                
                Specify versions by range:
                $ all-python -s 3.5 -e 3.8 -- -c 'print(type(u""))'
        ''')),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Optional: shell command execution
    parser.add_argument('-b', '--before', type=ShellCommand, default=NullShellCommand(),
                        help='execute shell commands before execute python script',
                        metavar='CMD')
    parser.add_argument('-E', '--exec', type=ShellCommand,
                        help='execute shell commands on each python versions',
                        metavar='CMD')
    parser.add_argument('-a', '--after', type=ShellCommand, default=NullShellCommand(),
                        help='execute shell commands after execute python script',
                        metavar='CMD')

    # Optional: python interpreter versions
    parser.add_argument('-s', '--min-version', type=Version, default=NullVersionMatcher(),
                        help='minimum python version')
    parser.add_argument('-e', '--max-version', type=Version, default=NullVersionMatcher(),
                        help='maximum python version')
    parser.add_argument('-v', '--version', type=MultiVersionMatcher, default=NullVersionMatcher(),
                        help='python versions')

    # Optional: python interpreter arguments
    parser.add_argument('python_args', nargs='*', help='python interpreter arguments')
    return parser.parse_args()


def main():
    try:
        args = parse_args()
        if all([args.exec, args.python_args]):
            raise InvalidArgument('--exec and python_args are exclusive')
        elif not any([args.exec, args.python_args]):
            raise InvalidArgument('must specify one argument of --exec or python_args')

        if args.python_args == ['bash']:
            # Show splash message.
            print(textwrap.dedent('''
                ====================   all-python (shell mode)   ====================
                You can use any linux commands on this shell.  For example, the following 
                commands are available.
                
                  apt        - install some software and libraries into this container.
                  all-python - run various versions of python with specified arguments.
                  exit       - exit this shell.
                
                Python interpreters are installed under the /opt/all-python/ directory.
                If you want to specify the version of python interpreter, please append 
                /opt/all-python/Python-{version}/bin/ directory to $PATH.
                
                See `all-python --help` for more info.
                Maintainer:  yuuki0xff  (https://github.com/yuuki0xff)
                GitHub:      https://github.com/yuuki0xff/all-python
                Bug Tracker: https://github.com/yuuki0xff/all-python/issues
                =====================================================================
            ''').strip())
            # Starting an interactive shell.
            os.execvp('bash', ['bash'])
            raise Exception('unreachable')

        repo = PythonRepository(prefix='/opt/all-python')

        def version_matcher(ver: Version) -> bool:
            return (
                    args.min_version.match(ver) and
                    args.max_version.match(ver) and
                    args.version.match(ver)
            )

        p = SectionPrinter()
        p.print('before', args.before.run())

        csp = CompactSectionPrinter()
        interpreters = repo.find(matcher=version_matcher)
        for py in sorted(interpreters, key=lambda py: py.version):
            if args.exec:
                cmd = args.exec
            elif args.python_args:
                cmd = PythonCommand(args.python_args)
            else:
                raise Exception('bug: --exec and python_args are None')

            try:
                out = cmd.run(py)
            except subprocess.CalledProcessError as e:
                # ignore error
                stdout = e.stdout.rstrip('\n')
                out = (
                    f'{stdout}\n\n'
                    f'Command returned non-zero exit status {e.returncode}\n'
                    f'Command: {e.cmd}'
                )
            csp.print(str(py.version), out)
        csp.close()

        p.print('after', args.after.run())
        return 0
    except InvalidArgument as e:
        print('ERROR: ' + e.args[0], file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print('ERROR: ' + str(e), file=sys.stderr)
        p = SectionPrinter(file=sys.stderr)
        p.print('stdout/stderr', e.stdout)


if __name__ == '__main__':
    exit(main())
