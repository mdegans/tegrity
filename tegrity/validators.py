import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

import tegrity

from typing import (
    Union,
    Sequence,
)

# from adduser.conf:
NAME_REGEX = re.compile(r"^[-a-z0-9]*$")
NAME_REGEX_SYSTEM = re.compile(r"^[a-zA-Z0-9]*$")
# todo: make more comprehensive list of dangerous groups, this is mostly to test
USERNAMES_RESTRICTED = ('root', 'nobody', 'daemon', 'sys')
GROUPS_RESTRICTED = USERNAMES_RESTRICTED
GECOS_RE = re.compile(r"^[a-zA-Z0-9_ ]*$")
ID_RESTRICTED = (0, 1)
ID_MAX = 65535
SHELLS = (
    '/bin/bash',
    '/bin/csh',
    '/bin/false',
    '/bin/ksh',
    '/bin/sh',
    '/bin/tcsh',
    '/bin/zsh',
    '/usr/sbin/nologin',
)
HOMES_PREFIXES = (
    '/home',
    '/var',
    '/run',
)  # anything else may work, but is probably a mistake

__all__ = [
    'validate_add_extra_groups',
    'validate_authorized_keys',
    'validate_gecos',
    'validate_group',
    'validate_home',
    'validate_ingroup',
    'validate_length',
    'validate_path',
    'validate_re',
    'validate_shell',
    'validate_uid_gid',
    'validate_username',
]


def validate_re(name, string, compiled_re):
    logger.debug(f'validating {name} {string}'
                 f' matches regex: {compiled_re.pattern}')
    if not re.match(compiled_re, string):
        raise ValueError(f"{string} does not match regex: {compiled_re.pattern}")


def validate_authorized_keys(keys: Union[Sequence, str]):
    logger.debug(f'validating authorized keys: {keys}')
    if isinstance(keys, str):
        keys = keys.split('\n')
    try:
        # noinspection PyProtectedMember
        tegrity.firstboot._validate_authorized_keys(authorized_keys=keys)
    except subprocess.CalledProcessError as err:
        raise ValueError(
            f'"{keys}" is an invalid set of authorized keys') from err


def validate_length(name: str, string: str, maxlen=1000, minlen=0):
    logger.debug(f'validating {minlen} < len({string}) < {maxlen}')
    if not minlen < len(string) < maxlen:
        raise ValueError(
            f"{name} must be longer than {minlen} "
            f"and shorter than {maxlen} characters")


def validate_username(username, system=False):
    # todo: check /etc/passwd on rootfs for pre-existing users
    # todo: add --system check to gui, rn system is always false
    regex = NAME_REGEX_SYSTEM if system else NAME_REGEX
    logger.debug(f'validating username: {username}')
    validate_re('username', username, regex)
    validate_length('username', username, maxlen=32)
    if username in USERNAMES_RESTRICTED:
        raise ValueError(
            f'username cannot be any of these: {" ".join(USERNAMES_RESTRICTED)}')


def validate_gecos(gecos: str):
    """
    validates a |gecos| entry, by length (max 260), number of segments,
    and ensures each segment is alphanumeric (underscores and spaces allowed)
    :raises: ValueError

    >>> validate_gecos('Michael de Gans,,,')
    >>> validate_gecos('Michael de Gans,,,,')
    Traceback (most recent call last):
      File "/usr/lib/python3.6/doctest.py", line 1330, in __run
        compileflags, 1), test.globs)
      File "<doctest __main__.validate_gecos[1]>", line 1, in <module>
        validate_gecos('Michael de Gans,,,,')
      File "/home/mdegans/PycharmProjects/tegrity_builder/tegrity/validators.py", line 43, in validate_gecos
        "too many commas in gecos entry")
    ValueError: too many commas in gecos entry
    """
    # https://www.linuxquestions.org/questions/linux-general-1/what-is-the-max-length-of-id-description-589053/
    logger.debug(f'validating gecos: {gecos}')
    validate_length('gecos', gecos, maxlen=260)
    segments = gecos.split(',')
    if len(segments) > 4:
        raise ValueError(
            "too many commas in gecos entry")
    for seg in segments:  # type: str
        validate_re('gecos segment', seg, GECOS_RE)


def validate_uid_gid(xid):
    logger.debug(f'validating uid: {xid}')
    xid = int(xid)
    if xid in ID_RESTRICTED:
        raise ValueError(f'uid/gid {xid} not allowed')
    if xid > ID_MAX:
        raise ValueError(f'uid/gid must be less than {ID_MAX}')


def validate_path(path, rootfs=None):
    logger.debug(f'validating path: {path} '
                 f'{"on rootfs " + rootfs if rootfs else ""}')
    if rootfs:
        path = os.path.relpath(path, os.path.sep)
        path = os.path.join(rootfs, path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} does not exist")
    return path


def validate_shell(shell, rootfs=None):
    logger.debug(f'validating shell: {shell} '
                 f'{"on rootfs " + rootfs if rootfs else ""}')
    if shell not in SHELLS:
        raise ValueError(f'{shell} not one of: {SHELLS}')
    path = validate_path(shell, rootfs=rootfs)
    if not os.access(path, os.X_OK):
        raise PermissionError(
            f'{path} not executable (rootfs extracted wrong?)')


def validate_home(home: str):
    logger.debug(f'validating home: {home}')
    if not any(home.startswith(p) for p in HOMES_PREFIXES):
        raise ValueError(
            f'home must start with one of: {" ".join(HOMES_PREFIXES)}')


def validate_group(group: str):
    logger.debug(f'validating group {group}')
    validate_re('group', group, NAME_REGEX)
    if group in GROUPS_RESTRICTED:
        raise ValueError(
            f'group cannot be any of: {" ".join(GROUPS_RESTRICTED)}')


def validate_ingroup(ingroup: str):
    logger.debug(f'validating ingroup {ingroup}')
    if ingroup == 'sudo':
        raise ValueError(
            'sudo should not be the primary group.'
            'Add it to add_extra_groups instead.')
    validate_group(ingroup)


def validate_add_extra_groups(add_extra_groups: str):
    groups = add_extra_groups.split(' ')
    for group in groups:
        validate_group(group)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
