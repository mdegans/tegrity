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
import os
import subprocess

import tegrity

from typing import (
    Iterable,
    MutableSet,
    Optional,
    Text,
)

# temporary folder to copy .deb files to:
DPKG_FOLDER = ('opt', 'tegrity', 'dpkg')
THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
APT_FIRSTBOOT_SCRIPT = os.path.join(THIS_FOLDER, '_apt_firstboot_dpkg.py')

REQUIREMENTS = {
    "bc",
    "build-essential",
    "libncurses5-dev",  # needed by tegrity.kernel so menuconfig works
    "qemu-user-static",  # needed by tegrity.qemu
}

USAGE = """usage examples:

  (assuming a folder "rootfs" exists in the current directory, like in Linux_for_Tegra)

  To upgrade the rootfs:
      tegrity-apt rootfs --upgrade
  To install nano (text editor) and blender (3d modeler) on a rootfs:
      tegrity-apt rootfs --install nano blender
  To remove blender and nano from a rootfs:
      tegrity-apt rootfs --remove nano blender
  To remove blender and nano *along with any configuration* from a rootfs:
      tegrity-apt rootfs --purge blender nano
  To install a series of debian packages on a rootfs:
      tegrity-apt rootfs --debs some_package.deb some_other_package.deb
"""

logger = logging.getLogger(__name__)

__all__ = [
    'list_installed',
    'update',
    'upgrade',
    'install',
    'remove',
    'purge',
    'ensure_requirements',
    'qemu_dpkg_install',
]


def list_installed(runner=None) -> MutableSet[Text]:
    """
    :returns: a MutableSet (eg. set()) of installed packages on the system
    :raises: subprocess.CalledProcessError if command fails

    >>> "apt" in list_installed()
    True
    """
    logger.debug("Checking for apt requirements...")
    runner = runner.run_cmd if runner else tegrity.utils.run
    cp = tegrity.utils.run(
        ("apt", "list", "--installed"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # to suppress the apt usage in script warning
        universal_newlines=True,
    )  # type: subprocess.CompletedProcess
    cp.check_returncode()
    return {line.split('/')[0] for line in cp.stdout.split('\n')}


def update(runner=None) -> subprocess.CompletedProcess:
    """
    :returns: subprocess.CompletedProcess instance for 'sudo apt-get update'
    :raises: subprocess.CalledProcessError if command fails
    """
    logger.info("Updating package information.")
    command = ('apt-get', 'update')
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


def upgrade(runner: tegrity.qemu.QemuRunner = None,
            dist_upgrade: bool = True,
            autoremove: bool = False,):
    logger.info(f"updating system at {runner.rootfs if runner else '/'}")
    command = ['apt-get', 'dist-upgrade' if dist_upgrade else 'upgrade', '-y']
    if autoremove:
        command.append('--autoremove')
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


def install(deps: Iterable[Text],
            runner: tegrity.qemu.QemuRunner = None,
            ) -> subprocess.CompletedProcess:
    """
    :returns: subprocess.CompletedProcess for subprocess.run() of:
              sudo apt-get install -y *sorted(set(deps))

    :arg deps: Iterable of apt dependencies

    :param runner: tegrity.qemu.QemuRunner to run the command with

    :raises: subprocess.CalledProcessError if command fails
    """
    command = ('apt-get', 'install', '-y', *sorted(set(deps)))
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


def remove(packages: Iterable[Text], runner: tegrity.qemu.QemuRunner = None):
    command = ('apt-get', 'remove', *sorted(set(packages)))
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


def purge(packages: Iterable[Text], runner: tegrity.qemu.QemuRunner = None):
    command = ('apt-get', 'purge', *sorted(set(packages)))
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


def clean(runner: tegrity.qemu.QemuRunner = None):
    command = ('apt-get', 'clean')
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


def autoremove(runner: tegrity.qemu.QemuRunner = None):
    command = ('apt-get', 'autoremove')
    if runner:
        return runner.run_cmd(command)
    else:
        return tegrity.utils.run(command)


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


def qemu_dpkg_install(runner: tegrity.qemu.QemuRunner, filenames: Iterable):
    source_filenames = sorted(filenames)
    if not source_filenames:
        logger.warning(
            "no filenames supplied to qemu_dpkg_install. doing nothing")
        return
    logger.info(f"installing {len(source_filenames)} .deb packages on "
                f"rootfs {runner.rootfs}")
    dest_filenames = []  # full path to copy location
    abspath_filenames = []  # chroot path to copy location
    dpkg_folder = os.path.join(runner.rootfs, *DPKG_FOLDER)
    try:
        for filename in source_filenames:
            dest = os.path.join(dpkg_folder, os.path.basename(filename))
            tegrity.utils.copy(filename, dest)
            dest_filenames.append(dest)
            abspath_filenames.append(
                os.path.join('/', *DPKG_FOLDER, os.path.basename(filename)))
            runner.run_cmd(('dpkg', '-i', *abspath_filenames)).check_returncode()
    except Exception as err:
        logger.error(
            f"dpkg install on rootfs had error. "
            f"cleaning up files in {dpkg_folder}...", err)
        for filename in dest_filenames:
            tegrity.utils.remove(filename)
        raise

# partially finished t0do from below:
# def firstboot_dpkg_install(rootfs, packages: Iterable[str]):
#     logger.info("setting up a first boot script to install apt packages")
#     if not os.path.isdir(rootfs):
#         raise NotADirectoryError(f"rootfs doesn't appear to exist at {rootfs}")
#     fsroot = os.path.abspath(os.sep)  # "/"
#     dpkg = os.path.join(rootfs, *DPKG_FOLDER)
#     rootfs_dpkg = os.path.join(fsroot, *DPKG_FOLDER)
#     os.makedirs(dpkg, mode=0o755)
#     tegrity.service.install()


def main(rootfs,
         apt_upgrade: Optional[bool] = None,
         apt_install: Optional[Iterable] = None,
         apt_remove: Optional[Iterable] = None,
         apt_purge: Optional[Iterable] = None,
         debs: Optional[Iterable] = None,):
    """
    Does apt operations on a rootfs.

    :arg rootfs: the rootfs to operate on
    :param apt_upgrade: whether to upgrade the system
    :param apt_install: optional iterable of packages to install
    :param apt_remove: optional iterable of packages to remove
    :param apt_purge: optional iterable of packages and configuration to remove
    :param debs: optional iterable of debian packages to install
    :return:
    """
    if not (apt_upgrade or apt_install or apt_remove or apt_purge or debs):
        raise ValueError("Nothing to do...")
    with tegrity.qemu.QemuRunner(rootfs) as runner:
        try:
            if apt_upgrade or apt_install:
                update(runner=runner).check_returncode()
            if apt_upgrade:
                upgrade(runner=runner).check_returncode()
            if apt_install:
                install(apt_install, runner=runner).check_returncode()
            if apt_remove:
                remove(apt_remove, runner=runner)
            if apt_purge:
                purge(apt_purge, runner=runner)
            if debs:
                qemu_dpkg_install(runner, debs)
            autoremove(runner)
        finally:
            clean(runner)


def cli_main():
    import argparse
    ap = argparse.ArgumentParser(
        description='utility to install or update Debian packages on a rootfs',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=USAGE,
    )

    ap.add_argument(
        'rootfs', help="the rootfs path to operate on")
    ap.add_argument(
        '--upgrade', help="does a full upgrade with --autoremove",
        dest='apt_upgrade',
        action='store_true')
    ap.add_argument(
        '--install', help="installs apt packages from online repos",
        dest='apt_install',
        nargs='+')
    ap.add_argument(
        '--remove', help="removes apt packages",
        dest='apt_remove',
        nargs='+')
    ap.add_argument(
        '--purge', help="removes apt packages and any associated configuration",
        dest='apt_purge',
        nargs='+')
    ap.add_argument(
        '--debs', help="a list of debian packages to install using dpkg",
        nargs='+',)

    main(**tegrity.cli.cli_common(ap))


if __name__ == '__main__':
    cli_main()
