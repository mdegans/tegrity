#!/usr/exe/python3 -sS

# Copyright 2019 Michael de Gans
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__doc__ = """This file is intended to be used as a first boot script to install
debian packages, either from file or from a repository. It relies on aptdcon."""
# todo: remove aptdcon dependency

import subprocess
import os

from typing import (
    Iterable,
)


def delete(files: Iterable):
    print("cleaning up packages")
    files = sorted(set(files))
    for file in files:
        if os.path.isfile(file):
            print(f"deleting {file}")
            os.remove(file)


def aptdcon_install(packages: Iterable, delete_debs=True):
    """installs packages using aptdcon (waits for apt to be free)"""
    packages = sorted(set(packages))
    print(f"Installing {' '.join(packages)}")
    packages_in_quotes = (f'"{p}"' for p in packages)
    command = ('aptdcon', '--hide-terminal', '--install', *packages_in_quotes)
# https://askubuntu.com/questions/132059/how-to-make-a-package-manager-wait-if-another-instance-of-apt-is-running/373478#373478
    # Hide Terminal is needed, else piping yes will cause issues.
    # – whitehat101 Mar 17 '16 at 17:58
    try:
        subprocess.run(command, input=b'yyyyy',).check_returncode()
    except FileNotFoundError as err:
        raise FileNotFoundError("is aptdcon installed?") from err
    if delete_debs:
        delete(packages)


def main(packages, no_delete=False):
    aptdcon_install(packages, not no_delete)


def cli_main(*args):
    import argparse
    ap = argparse.ArgumentParser(
        description="installs apt packages (using aptdcon)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""usage examples:
  {file} foo.deb bar.deb
""".format(file=__file__))

    ap.add_argument(
        'packages', nargs='+', help="a list of debian packages")
    ap.add_argument(
        '--no-delete', dest='delete_debs', action='store_false',
        help="do not delete packages after successful install")

    args = ap.parse_args()

    aptdcon_install(args.packages)


if __name__ == '__main__':
    cli_main()
