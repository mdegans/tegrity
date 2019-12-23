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

import getpass
import logging
import os
import shutil
import subprocess
import time

from typing import (
    Any,
    Callable,
    Iterable,
    Optional,
    Sequence,
)

import tegrity

# these really live in firstboot.py because firstboot.py needs to exist on it's
# own and uses these functions:
# noinspection PyProtectedMember
from tegrity.firstboot import (
    _yes_or_no as yes_or_no,
    _run_one as run,
    _mkdir as mkdir,
    _chmod as chmod,
    _copy as copy,
    _remove as remove,
)

__all__ = [
    'chmod',
    'chooser',
    'copy',
    'ensure_sudo',
    'estimate_size',
    'join_and_check',
    'mkdir',
    'move',
    'real_username',
    'remove',
    'rename',
    'run',
    'yes_or_no',
]

logger = logging.getLogger(__name__)


def real_username() -> str:
    """:returns" the real username running the script"""
    return os.environ['SUDO_USER'] \
        if "SUDO_USER" in os.environ \
        else getpass.getuser()


def chooser(list_of_things: Sequence, name_of_things: str,
            formatter: Optional[Callable[[Any], str]] = None):
    """
    Prompts for a thing from a Sequence (list, etc) of things.
    Returns the first thing automatically if only one item in the
    |list_of_things| Sequence.

    :param list_of_things: sequence of things to choose from
    :param name_of_things: plural name of the thing
    :param formatter: formatter to convert the thing to a string

    :returns: chosen item from the list
    """
    if len(list_of_things) == 1:
        # this is cheap, but works most of the time.
        # todo, add option for singular
        if name_of_things.endswith('s'):
            name_of_things = name_of_things[:-1]
        thing = list_of_things[0]
        logger.debug(f"Only one {name_of_things} found: {thing}")
        return thing if not formatter else formatter(thing)
    choice = None
    while choice not in range(len(list_of_things)):
        print(f"Please choose from the following {name_of_things}:")
        for number, thing in enumerate(list_of_things):
            print(number, thing if not formatter else formatter(thing))
        try:
            choice = int(input(f"Choice (0-{len(list_of_things) - 1})"))
        except ValueError:
            logger.error("Choice must be a number.")
    return list_of_things[choice]


def backup(path) -> str:
    """renames a path with a backup timestamp"""
    path_backup = f"{path}.backup.{int(time.time())}"
    logger.info(f"Backing up {path} to {path_backup}")
    os.rename(path, path_backup)
    return path_backup


def move(source, destionation):
    """wraps shutil.move() and logs to backup"""
    logger.debug(f"moving {source} to {destionation}")
    shutil.move(source, destionation)


rename = move


def join_and_check(path, *sub) -> str:
    """joins a path with os.path.join and ensures it os.path.exists()"""
    path = os.path.join(path, *sub)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{os.path.join(*sub)} not found in {path}. "
            f"{tegrity.err.BUNDLE_REINSTALL}")
    return path


def estimate_size(folder) -> int:
    """gets the size estimate of a folder in GB (stupid storage manufacturer
    powers of 1000) using du"""
    logger.info(f"Estimating size of {folder}")
    cp = tegrity.utils.run(
        ('du', '-s', '-BGB', folder),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        cp.check_returncode()
    except subprocess.CalledProcessError:
        logger.error(cp.stderr.decode())
        logger.error(
            "image size estimate might not be accurate. "
            "Are you running as root?")
        raise
    # get the size in GB from the output
    size, _ = cp.stdout.split()
    # strip the end off and convert to integer
    size = int(size.decode()[:-2])

    return size


def mount(source, target,
          type_: Optional[str] = None,
          options: Optional[Iterable[str]] = None,
          ) -> subprocess.CompletedProcess:
    logger.info(f"Mounting {target}")
    command = ['mount']
    if type_:
        command.extend(('-t', str(type_)))
    if options:
        command.append('-o')
        command.append(','.join(sorted(options)))
    command.extend((source, target))
    return tegrity.utils.run(command)


def umount(target) -> subprocess.CompletedProcess:
    """
    unmounts a target path
    :arg target: the target to unmount
    :return: subprocess.CompletedProcess of the unmount command
    """
    logger.info(f"Unmounting: {target}")
    return tegrity.utils.run(('umount', target))


def ensure_sudo() -> str:
    """ensures user is root and SUDO_USER is in os.environ,
    :returns: the real username (see real_username())
    """
    # if we aren't root, or don't have access to host environment variables...
    username = real_username()
    uid = os.getuid()
    if username == "root":
        raise EnvironmentError(
            "Could not look up SUDO_USER. Are you running using 'sudo su'? "
            "This is currently unsupported since this script needs to look up "
            "your real username in order to find your ~/nvsdk/sdkm.db file and "
            "su clears the environment.")
    if uid != 0:
        raise PermissionError("this script needs sudo")
    return username


def ensure_config_path(
        path=tegrity.DEFAULT_CONFIG_PATH,
        mode=tegrity.CONFIG_PATH_MODE,):
    """creates a config/cache/log folder in ~ with the proper permissions."""
    logger.info(f"Ensuring {path} exists")
    if os.path.exists(path):
        if os.path.isdir(path):
            tegrity.utils.chmod(path, mode)
        else:
            raise FileExistsError(
                f"{path} is supposed to be a directory, please relocate this "
                f"file if not needed or modify {tegrity.__name__} source"
            )
        path_stat = os.stat(path)
        if not path_stat.st_gid == 0 and path_stat.st_gid == 0:
            logger.warning(
                f"{path} does not appear to be owned by root. "
                f"This is fine, but please be aware that sometimes sensitive "
                f"information is dumped into log files.")
    else:
        tegrity.utils.mkdir(path, mode)


def ensure_system_requirements(cross_prefix=None):
    """ensures system requirements are installed and returns cross prefix"""
    logger.info("Ensuring system requirements...")
    tegrity.utils.ensure_sudo()
    tegrity.apt.ensure_requirements()
    ensure_config_path()
    return tegrity.toolchain.ensure(cross_prefix)


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
