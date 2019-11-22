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

import logging
import subprocess

import tegrity

from typing import (
    Iterable,
    Text,
    MutableSet,
)

REQUIREMENTS = {"git", "build-essential", "bc", "libncurses5-dev"}

logger = logging.getLogger(__name__)


__all__ = [
    'list_installed',
    'update',
    'install',
    'ensure_requirements',
]


def list_installed() -> MutableSet[Text]:
    """
    :returns: a MutableSet (eg. set()) of installed packages on the system
    :raises: subprocess.CalledProcessError if command fails

    >>> "apt" in list_installed()
    True
    """
    logger.debug("Checking for apt requirements...")
    cp = tegrity.utils.run(
        ("apt", "list", "--installed"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # to suppress the apt usage in script warning
        universal_newlines=True,
    )  # type: subprocess.CompletedProcess
    cp.check_returncode()
    return {line.split('/')[0] for line in cp.stdout.split('\n')}


def update() -> subprocess.CompletedProcess:
    """
    :returns: subprocess.CompletedProcess instance for 'sudo apt-get update'
    :raises: subprocess.CalledProcessError if command fails
    """
    command = ('apt-get', 'update')
    cp = tegrity.utils.run(command)
    cp.check_returncode()
    return cp


def install(deps: Iterable[Text]) -> subprocess.CompletedProcess:
    """
    :returns: subprocess.CompletedProcess for subprocess.run() of:
              sudo apt-get install -y *sorted(set(deps))

    :arg deps: Iterable of apt dependencies

    :raises: subprocess.CalledProcessError if command fails
    """
    command = ('apt-get', 'install', '-y', *sorted(set(deps)))
    logger.debug(f"Running: {' '.join(command)}")
    cp = subprocess.run(command)
    cp.check_returncode()
    return cp


def ensure_requirements():
    """
    ensures apt package requirements are met

    :raises: subprocess.CalledProcessError (most likely because of not being run
    as root).
    """
    missing = tegrity.apt.REQUIREMENTS - tegrity.apt.list_installed()
    if missing:
        logger.error(f"Missing packages: {' '.join(sorted(missing))}")
        response = input(
            "Do you wish to install the missing packages using apt?"
            "('y' to install or 'n' for the command to do it manually)").lower()
        if response[0] == 'y':
            try:
                tegrity.apt.update()
            except subprocess.CalledProcessError as err:
                if "Permission denied" in err.stdout:
                    tegrity.utils.ensure_sudo()
                raise
            tegrity.apt.install(missing)
        else:
            logger.error(
                f"To continue manually, you must run: \n"
                f"sudo apt install {' '.join(sorted(missing))}")


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
