#!/usr/bin/python3 -sS

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

# many thanks to this wiki:
# https://wiki.debian.org/QemuUserEmulation

import os
import logging
import subprocess
import shutil

from typing import (
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Union,
)

import tegrity

logger = logging.getLogger(__name__)

# default arch (used to find qemu static binary)
ARCH = 'aarch64'


def default_mount_kwargs(rootfs: str) -> List[Dict[str, Union[List[str], str]]]:
    """
    :returns: a default mount configuration for a functional chroot as a list of
    keyword arguments for tegrity.utils.mount()  Used internally by QemuRunner,
    but can also be used on it's own.

    default configuration:

    mount -t sysfs -o ro,nosuid,nodev,noexec,relatime none rootfs/sys
    mount -t proc -o ro,nosuid,nodev,noexec,relatime none rootfs/proc
    mount -o bind,ro /dev rootfs/dev
    mount -t devpts -o rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 \
        none rootfs/dev/pts
    mount -o bind,ro /etc/resolv.conf rootfs/run/resolvconf/resolv.conf
    mount -t tmpfs tmpfs rootfs/tmp

    note: that the options are not intended to sandbox, rather to prevent the
    host from *accidental* damage.

    :param rootfs: path to the rootfs
    """
    run_resolv = os.path.join(rootfs, 'run', 'resolvconf', 'resolv.conf')
    etc_resolv = os.path.join(rootfs, 'etc', 'resolv.conf')
    if os.path.exists(run_resolv) and os.path.islink(etc_resolv):
        resolv_target = run_resolv
    elif os.path.exists(etc_resolv) and not os.path.islink(etc_resolv):
        resolv_target = etc_resolv
    else:
        resolv_target = None
        logger.warning(
            f"{run_resolv} or {etc_resolv} not found. "
            f"network may not be reachable")
    list_of_kwargs = [
        # /sys
        {
            'source': 'sysfs',
            'target': os.path.join(rootfs, 'sys'),
            'type_': 'sysfs',
            'options': ['ro', 'nosuid', 'nodev', 'noexec', 'relatime'],
        },
        # /proc
        {
            'source': 'proc',
            'target': os.path.join(rootfs, 'proc'),
            'type_': 'proc',
            'options': ['ro', 'nosuid', 'nodev', 'noexec', 'relatime'],
        },
        # /dev
        {
            'source': '/dev',
            'target': os.path.join(rootfs, 'dev'),
            'options': ['bind', 'ro'],
        },
        # /dev/pts
        {
            'source': 'devpts',
            'target': os.path.join(rootfs, 'dev', 'pts'),
            'type_': 'devpts',
            'options': [
                "rw",
                "nosuid",
                "noexec",
                "relatime",
                "gid=5",
                "mode=620",
                "ptmxmode=000",
            ]
        },
        # /tmp
        {
            'source': 'tmpfs',
            'target': os.path.join(rootfs, 'tmp'),
            'type_': 'tmpfs',
            # normally noexec and some other stuff might go here, but we'll use
            # /tmp inside the rootfs for scripts, so we need to execute from it
        },
    ]
    if resolv_target:
        # resolv.conf
        list_of_kwargs.append({
            'source': '/etc/resolv.conf',
            'target': resolv_target,
            'options': ['bind', 'ro']
        })
    return list_of_kwargs


class QemuRunner(object):
    def __init__(self, rootfs: Union[str, os.PathLike],
                 arch: str = ARCH,
                 qemu: str = None,
                 mount_kwargs=None,
                 additional_mounts=None,
                 userspec: str = None):
        """
        :arg rootfs: the rootfs path (eg. .../Linux_for_Tegra/rootfs)
        :param arch: the architecture of qemu binary to use (qemu-|arch|-static)
        to find the qemu binary
        :param qemu: path to qemu binary, if not |arch|
        :param mount_kwargs: an Iterable of kwargs (eg, a list of dicts).
        if not supplied, this is generated by tegrity.qemu.default_mount_kwargs()
        with the rootfs parameter supplied.
        :type mount_kwargs: Iterable[Mapping[str, Union[Iterable[str], str]]]
        :param additional_mounts: extends the default mounts, in the same format
        as mount_kwargs
        __exit__ in reverse order.
        :type additional_mounts: Iterable[Mapping[str, Union[Iterable[str], str]]]
        :param userspec: USER:GROUP string (see chroot manual)
        """
        # all this checking is perhaps not pythonic, but in this case it is
        # perhaps better to fail fast than start mounting and running
        # things.
        self.rootfs = str(rootfs)
        if not os.path.isdir(self.rootfs):
            raise NotADirectoryError(
                f"{self.rootfs} needs to be a rootfs directory "
                f"(tarball not supported for now)")
        if not (arch or qemu):
            raise ValueError("arch or qemu must be specified")
        self.arch = arch if arch else qemu.split('-')[1]
        if arch and qemu:
            raise ValueError(
                "either arch or qemu must be specified, but not both.")
        if qemu:
            self.qemu = str(qemu)
        else:
            self.qemu = shutil.which(f'qemu-{self.arch}-static')
        if not os.path.isfile(self.qemu):
            raise FileNotFoundError(f'{self.qemu} not found')
        if not os.access(self.qemu, os.X_OK):
            raise PermissionError(f"{self.qemu} not executable")
        if mount_kwargs:
            self.mount_kwargs = list(mount_kwargs)
        else:
            self.mount_kwargs = default_mount_kwargs(rootfs)
        if additional_mounts:
            self.mount_kwargs.extend(additional_mounts)
        if userspec:
            if ':' not in userspec or '-' in userspec:
                raise ValueError("Userspec format invalid. see chroot manual")
        self.userspec = userspec
        self.tmp = os.path.join(rootfs, 'tmp')
        self._qemu_copied = False
        self._mounted = []  # unmounted on __exit__
        self._scripts = []  # deleted from rootfs /tmp on __exit__

    def __enter__(self):
        try:
            # copy qemu to rootfs, if it doesn't exist on rootfs,
            # otherwise bind mount it, so as not to overwrite.
            target = os.path.join(
                self.rootfs, 'usr', 'bin', os.path.basename(self.qemu))

            if os.path.isfile(target):
                tegrity.utils.mount(
                    self.qemu, target, options=['bind', 'ro']
                ).check_returncode()
                self._mounted.append(target)

            else:
                tegrity.utils.copy(self.qemu, target)
                self._qemu_copied = target

            # mount filesystems
            for kwargs in self.mount_kwargs:
                target = kwargs['target']
                tegrity.utils.mount(**kwargs).check_returncode()
                self._mounted.append(target)

        # if there were *any* errors, clean up and raise
        except Exception as err:
            logger.error(
                f"{__class__.__name__}.__enter__ had error. Cleaning up.", err,)
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(
                f"QemuRunner had error. Cleaning up.",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        if self._qemu_copied:
            tegrity.utils.remove(self._qemu_copied)
        # unmount filesystems in reverse order
        for mount in reversed(self._mounted):
            tegrity.utils.umount(mount)
        for script in self._scripts:
            try:
                tegrity.utils.remove(script)
            except Exception as err:
                logger.error(f"removing {script} failed", err)

    def _base_command(self, userspec: Optional[str] = None) -> List[str]:
        command = ['chroot']
        if userspec:
            command.append(f'--userspec={userspec}')
        elif self.userspec:
            command.append(f'--userspec={self.userspec}')
        command.append(self.rootfs)
        return command

    def enter_chroot(self, userspec: Optional[str] = None):
        tegrity.utils.run(
            self._base_command(userspec=userspec)
        ).check_returncode()

    def run_cmd(self, command: Iterable, userspec=None,
                **kwargs) -> subprocess.CompletedProcess:
        cmd = self._base_command(userspec=userspec)
        cmd.extend(command)
        return tegrity.utils.run(command, **kwargs)

    def run_script(self, script, *options,
                   userspec: Optional[str] = None,
                   ) -> subprocess.CompletedProcess:
        dest = os.path.join(self.tmp, script)
        tegrity.utils.copy(script, dest)
        self._scripts.append(dest)
        dest_in_chroot = os.path.join('/tmp', script)
        return self.run_cmd((dest_in_chroot, *options), userspec=userspec)


def main(rootfs: str,
         command: Optional[Iterable[str]] = None,
         script: Optional[Sequence[str]] = None,
         enter: Optional[bool] = None,
         arch: str = None,
         qemu: str = None,
         userspec: Optional[str] = None,):
    if not (enter or command or script):
        raise ValueError(
            "command and/or scripts must be supplied, and/or enter True")
    with QemuRunner(
            rootfs,
            userspec=userspec,
            arch=arch,
            qemu=qemu,
    ) as runner:
        if command:
            runner.run_cmd(command)
        if script:
            runner.run_script(*script)
        if enter:
            runner.enter_chroot()


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description="utility to modify a rootfs using qemu and chroot",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,)

    ap.add_argument(
        'rootfs', help='path to the rootfs')
    ap.add_argument(
        '--command', help="run a command inside chroot",
        nargs='+')
    ap.add_argument(
        '--script', help="run a script (with optional arguments)",
        nargs='+')
    ap.add_argument(
        '--enter', help='run commands interactively in chroot',
        action='store_true')
    ap.add_argument(
        '--userspec', help="USER:GROUP (ID or name) to use inside chroot (see "
        "chroot manual for details)")
    ap.add_argument(
        '--arch', help="architecture to use (to find qemu binary)",
        default=ARCH)
    ap.add_argument(
        '--qemu', help="path to custom qemu static binary to copy or bind mount "
        "into the rootfs (default is the one found in path using --arch)")

    # ensure requirements are met
    tegrity.apt.ensure_requirements()

    # add --log-file and --verbose
    main(**tegrity.cli.cli_common(ap))


if __name__ == '__main__':
    cli_main()