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

import hashlib
import logging
import os
import pathlib
import subprocess

import tegrity.utils

from typing import (
    Iterable,
    List,
    MutableSet,
    Optional,
    Text,
    Union,
)

# temporary folder to copy .deb files to:
DPKG_FOLDER = ('opt', 'tegrity', 'dpkg')
THIS_FOLDER = os.path.dirname(os.path.abspath(__file__))
APT_FIRSTBOOT_SCRIPT = os.path.join(THIS_FOLDER, '_apt_firstboot_dpkg.py')

REQUIREMENTS = {
    "bc",
    "build-essential",
    "libncurses5-dev",  # needed by tegrity.kernel so menuconfig works
    "python",  # required by some sdkmanager scripts but not listed in .deb deps
    "python3-pip",  # needed to install tegrity with install.py
    "qemu-user-static",  # needed by tegrity.qemu
    'proot',  # needed to avoid elevated privileges requirements
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


def list_(runner=tegrity.utils,
          installed=False,
          sorted_=False,
          ) -> Union[MutableSet[Text], List[Text]]:
    """
    runs: apt list

    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module
    :param installed: same as list_installed(), returns installed packages
    instead of available packages
    :param sorted_: returns a list in alphabetical order, rather than a Set

    :returns: a MutableSet (eg. set()) of available packages
    :raises: subprocess.CalledProcessError if command fails
    >>> "apt" in list_()
    True
    """
    logger.debug(f"checking{' installed ' if installed else ' available '}"
                 f"apt packages...")
    command = ["apt", "list"]
    if installed:
        command.append('--installed')
    cp = runner.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # to suppress the apt usage in script warning
        universal_newlines=True,
    )  # type: subprocess.CompletedProcess
    cp.check_returncode()
    if sorted_:
        return [line.split('/')[0] for line in cp.stdout.split('\n')]
    return {line.split('/')[0] for line in cp.stdout.split('\n')}


def list_installed(runner=tegrity.utils,
                   sorted_=False,
                   ) -> Union[MutableSet[Text], List[Text]]:
    """
    runs: apt list --installed

    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module
    :param sorted_: returns a list in alphabetical order, rather than a Set

    :returns: a MutableSet (eg. set()) of available packages
    :raises: subprocess.CalledProcessError if command fails
    >>> "apt" in list_installed()
    True
    """
    return list_(runner=runner, installed=True, sorted_=sorted_)


def update(runner=tegrity.utils) -> subprocess.CompletedProcess:
    """
    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module

    :returns: a subprocess.CompletedProcess for the command
    :raises: subprocess.CalledProcessError if command fails
    """
    return runner.run(('apt-get', 'update'))


def upgrade(runner=tegrity.utils,
            dist_upgrade: bool = True,
            autoremove_: bool = False,) -> subprocess.CompletedProcess:
    """
    runs: apt-get upgrade

    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module
    :param dist_upgrade: dist-upgrade instead of upgrade. see apt-get manual
    :param autoremove_: adds --autoremove, see apt-get manual

    :returns: a subprocess.CompletedProcess for the command
    :raises: subprocess.CalledProcessError if command fails
    """
    command = ['apt-get', 'dist-upgrade' if dist_upgrade else 'upgrade', '-y']
    if autoremove_:
        command.append('--autoremove')
    return runner.run(command)


def install(packages: Iterable[Text],
            runner=tegrity.utils,
            no_install_recommends=False,
            ) -> subprocess.CompletedProcess:
    """
    runs: apt-get install -y *sorted(set(packages))

    :arg packages: Iterable of apt package names
    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module
    :param no_install_recommends: does not install recommended packages
    see apt manual for --no-install-recommends

    :returns: a subprocess.CompletedProcess for the command
    :raises: subprocess.CalledProcessError if command fails
    """
    command = ['apt-get', 'install', '-y']
    if no_install_recommends:
        command.append('--no-install-recommends')
    command.extend(sorted(set(packages)))
    return runner.run(command)


def remove(packages: Iterable[Text],
           runner=tegrity.utils,
           ) -> subprocess.CompletedProcess:
    """
    runs: apt-get remove *sorted(set(packages))

    :arg packages: Iterable of apt package names
    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module

    :returns: a subprocess.CompletedProcess for the command
    :raises: subprocess.CalledProcessError if command fails
    """
    command = ('apt-get', 'remove', '-y', *sorted(set(packages)))
    return runner.run(command)


def purge(packages: Iterable[Text],
          runner=tegrity.utils,
          ) -> subprocess.CompletedProcess:
    """
    runs: apt-get purge *sorted(set(packages))

    :arg packages: Iterable of apt package names
    :param runner: object/module with .run() method such as
    tegrity.utils, tegrity.qemu.QemuRunner or the subprocess module

    :returns: a subprocess.CompletedProcess for the command
    :raises: subprocess.CalledProcessError if command fails
    """
    command = ('apt-get', 'purge', '-y', *sorted(set(packages)))
    return runner.run(command)


def clean(runner=tegrity.utils) -> subprocess.CompletedProcess:
    return runner.run(('apt-get', 'clean'))


def autoremove(runner=tegrity.utils) -> subprocess.CompletedProcess:
    return runner.run(('apt-get', 'autoremove'))


def _fix_sources(rootfs, board_id):
    sources_list = os.path.join(rootfs, *tegrity.settings.NV_SOURCES_LIST)
    logger.debug(f"overwriting {sources_list}")
    try:
        with open(sources_list, 'w') as sources_list:
            soc = tegrity.settings.BOARD_ID_TO_SOC[board_id]
            sources_list.write(
                tegrity.settings.NV_SOURCES_LIST_TEMPLATE.format(soc=soc))
    except FileNotFoundError as err:
        raise FileNotFoundError(
            f"could not find {sources_list} in rootfs") from err


def _install_ota_key(rootfs):
    logger.debug(f'installing ota key on rootfs: {rootfs}')
    rootfs = pathlib.Path(rootfs)
    # really, this should be from a keyserver
    key = rootfs.parent.joinpath('nv_tegra', 'jetson-ota-public.key')
    logger.debug(f'ota key source: {key}')
    tegrity.download.verify(
        key, tegrity.settings.JETSON_OTA_KEY_SHA512, hashlib.sha512)
    dest = rootfs.joinpath(
        'etc', 'apt', 'trusted.gpg.d', 'jetson-ota-public.asc')
    logger.debug(f'ota key dest: {dest}')
    try:
        tegrity.utils.remove(dest)
    except FileNotFoundError:
        pass
    tegrity.utils.copy(key, dest)


def enable_nvidia_ota(rootfs):
    """patches apt sources on a |rootfs| to enable ota updates. For now, the apt
    key must already be installed (apply_binaries.sh does this)"""
    board_id = tegrity.db.autodetect_hwid(pathlib.Path(rootfs).parent)
    _install_ota_key(rootfs)
    _fix_sources(rootfs, board_id)


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
            runner.run(('dpkg', '-i', *abspath_filenames)).check_returncode()
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
         nvidia_ota: Optional[bool] = None,
         proot: Optional[bool] = None,
         apt_upgrade: Optional[bool] = None,
         apt_autoremove: Optional[bool] = True,
         apt_install: Optional[Iterable] = None,
         no_install_recommends: Optional[bool] = False,
         apt_remove: Optional[Iterable] = None,
         apt_purge: Optional[Iterable] = None,
         apt_clean: Optional[bool] = True,
         debs: Optional[Iterable] = None,):
    """
    Does apt operations on a rootfs.

    :arg rootfs: the rootfs to operate on
    :param nvidia_ota: patch apt sources on an l4t rootfs with board id
    :param proot: uses proot instead of chroot (no need for root permissions)
    :param apt_upgrade: whether to upgrade the system
    :param apt_autoremove: does an apt autoremove at the end, before apt clean
    :param apt_install: optional iterable of packages to install
    :param no_install_recommends: see install()
    :param apt_remove: optional iterable of packages to remove
    :param apt_purge: optional iterable of packages and configuration to remove
    :param apt_clean: do an apt clean at the end (default True)
    :param debs: optional iterable of debian packages to install
    """
    if nvidia_ota:
        enable_nvidia_ota(rootfs)
    if not (apt_upgrade or apt_install or apt_remove or apt_purge or debs):
        return
    runner_cls = tegrity.qemu.ProotRunner if proot else tegrity.qemu.QemuRunner
    with runner_cls(rootfs) as runner:
        try:
            if apt_upgrade or apt_install:
                update(runner=runner).check_returncode()
            if apt_upgrade:
                upgrade(runner=runner).check_returncode()
            if apt_install:
                install(
                    apt_install,
                    runner=runner,
                    no_install_recommends=no_install_recommends,
                ).check_returncode()
            if apt_remove:
                remove(apt_remove, runner=runner)
            if apt_purge:
                purge(apt_purge, runner=runner)
            if debs:
                qemu_dpkg_install(runner, debs)
            if apt_autoremove:
                autoremove(runner)
        finally:
            if apt_clean:
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
        '--nvidia-ota', help="patches nvidia apt sources list with correct SOC"
        " id so OTA updates work before first boot.",
        action='store_true')
    ap.add_argument(
        '--proot', help="use proot instead of chroot (no root permisions needed)",
        action='store_true',
        default=tegrity.settings.IN_DOCKER,)
    ap.add_argument(
        '--upgrade', help="does a full upgrade with --autoremove",
        dest='apt_upgrade',
        action='store_true')
    ap.add_argument(
        '--install', help="installs apt packages from online repos",
        dest='apt_install',
        nargs='+')
    ap.add_argument(
        '--no-install-recommends', help='no recommended packages. see apt manual',
        action='store_true')
    ap.add_argument(
        '--remove', help="removes apt packages",
        dest='apt_remove',
        nargs='+')
    ap.add_argument(
        '--purge', help="removes apt packages and any associated configuration",
        dest='apt_purge',
        nargs='+')
    ap.add_argument(
        '--no-clean', help='does no apt clean at the end', dest='apt_clean',
        action='store_false')
    ap.add_argument(
        '--debs', help="a list of debian packages to install using dpkg",
        nargs='+',)

    main(**tegrity.cli.cli_common(ap, ensure_sudo=False))


if __name__ == '__main__':
    cli_main()
