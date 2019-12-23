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
import sqlite3
import pathlib

from typing import (
    Callable,
)

import tegrity

from tegrity.settings import (
    BOARD_ID_TO_SOC,
    L4T_ROOTFS_SHA512,
    L4T_ROOTFS_URL,
    NV_SOURCES_LIST,
    NV_SOURCES_LIST_TEMPLATE,
    UBUNTU_BASE_SHA_256,
    UBUNTU_BASE_URL,

)

logger = logging.getLogger(__name__)


# please customize these if they are outdated.
# new sha512 sums can be generated with python's hashlib module or
# the sha512sum command

# todo: cache downloads in ~/.tegrity to avoid hammering Nvidia's servers

def modify_sources(rootfs, board_id):
    sources_list = os.path.join(rootfs, *NV_SOURCES_LIST)
    logger.debug(f"overwriting {sources_list}")
    try:
        with open(sources_list, 'w') as sources_list:
            soc = BOARD_ID_TO_SOC[board_id]
            sources_list.write(NV_SOURCES_LIST_TEMPLATE.format(soc=soc))
    except FileNotFoundError as err:
        raise FileNotFoundError(
            f"could not find {sources_list} in rootfs") from err


def get_path(bundle: sqlite3.Row):
    """:returns: the path to the rootfs of the |bundle|"""
    l4t_path = tegrity.db.get_l4t_path(bundle)
    return tegrity.utils.join_and_check(l4t_path, "rootfs")


def ubuntu_base_reset(rootfs: str, source: str = None, sha256: str = None):
    """resets a |rootfs| to ubuntu base if not |source|
    :param sha256: the sha256 of the paremeter. Deprecated in favor of automatic
    verification using .asc file and Canonical's GPG key.
    todo: test this"""
    if not source:
        source = UBUNTU_BASE_URL
        sha256 = UBUNTU_BASE_SHA_256
    logger.debug(f"resetting {rootfs} to Ubuntu Base from url {source} "
                 f"and verifying using sha256: {sha256}")
    if os.path.exists(rootfs):
        tegrity.utils.backup(rootfs)
        tegrity.download.extract(
            source, rootfs,
            hasher=hashlib.sha256 if sha256 else None,
            hexdigest=sha256)


def reset(rootfs: str,
          source: str = None,
          source_hasher: Callable = None,
          source_hexdigest: str = None,
          ubuntu_base=False):
    """resets a rootfs for a |bundle| to stock, backing up the old one
    :arg rootfs: path to the rootfs to reset
    :param source: a source tarball (local or remote dir or tarball to copy or
    extract from).
    :param source_hasher: eg hashlib.md5
    :param source_hexdigest: the hexdigest expected (see hashlib docs)
    :param ubuntu_base: the same as using ubuntu_base_reset directly
    apt to get packages from Nvidia.
    """
    # make sure we don't accidentally reset /
    realroot = os.path.abspath(os.sep)  # / on unix, c:\ on windows
    if rootfs == realroot:
        raise tegrity.err.InSanityError(
            f"Can't reset {realroot}")
    if ubuntu_base:
        return ubuntu_base_reset(rootfs, source)
    logger.info(f"resetting rootfs{' from ' + source if source else ''}")

    if source:
        # download, extract, or copy it
        # todo: refactor this:
        if source.startswith("http"):
            if not source.startswith("https"):
                logger.warning(f"{source} is a http url. changing to https")
                source = f"https{source[4:]}"
            tegrity.utils.backup(rootfs)
            tegrity.download.extract(
                source, rootfs,
                hasher=source_hasher,
                hexdigest=source_hexdigest,)
        elif os.path.isfile(source):
            tegrity.utils.backup(rootfs)
            tegrity.download.extract(
                source, rootfs,
                hasher=source_hasher,
                hexdigest=source_hexdigest,)
        elif os.path.isdir(source):
            if not os.path.exists(os.path.join(source, 'etc')) and \
                    os.path.exists(os.path.join(source, 'bin')):
                raise tegrity.err.InSanityError(
                    "/etc/ or /bin/ not found. This doesn't look like a rootfs")
            tegrity.utils.backup(rootfs)
            tegrity.utils.copy(source, rootfs)
        return

    tegrity.utils.backup(rootfs)
    tegrity.download.extract(
        L4T_ROOTFS_URL, rootfs,
        hasher=hashlib.sha512,
        hexdigest=L4T_ROOTFS_SHA512,
    )


def apply_binaries(rootfs: os.PathLike, target_overlay=False):
    """runs the apply_binaries.sh script within a Linux_for_Tegra folder"""
    rootfs = pathlib.Path(os.path.abspath(rootfs))
    l4t_path = rootfs.parent
    if not os.path.isdir(l4t_path):
        raise FileNotFoundError(f"{l4t_path} not found")
    rootfs = os.path.join(l4t_path, 'rootfs')
    if not os.path.isdir(rootfs):
        raise FileNotFoundError(f"{rootfs} not found")
    script = tegrity.utils.join_and_check(l4t_path, 'apply_binaries.sh')
    if not os.path.isfile(script):
        raise FileNotFoundError(f"{script} not found")
    command = [script, ]
    if target_overlay:
        command.append('-t')
    command.extend(('-r', rootfs))
    tegrity.utils.run(command, cwd=l4t_path).check_returncode()


def main(rootfs,
         source=None,
         source_sha512=None,
         fix_sources=False,
         do_apply_binaries=False,
         target_overlay=False):
    if source == 'l4t':
        reset(rootfs)
    elif source == 'ubuntu_base':
        reset(rootfs, ubuntu_base=True)
    elif source:
        reset(rootfs,
              source=source,
              source_hasher=hashlib.sha512 if source_sha512 else None,
              source_hexdigest=source_sha512)
    if do_apply_binaries:
        try:
            apply_binaries(rootfs, target_overlay=target_overlay)
        except FileNotFoundError as err:
            raise FileNotFoundError(
                f"could not apply binaries. Please run Nvidia's apply_binaries.sh "
                f"script on your rootfs manually.") from err
    if fix_sources:
        try:
            modify_sources(
                rootfs,
                tegrity.db.autodetect_hwid(pathlib.Path(rootfs).parent))
        except Exception as err:
            raise RuntimeError(
                "Failed to modify apt sources on rootfs.") from err


def cli_main():
    import argparse
    ap = argparse.ArgumentParser(
        description="resets and prepares a rootfs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ap.add_argument(
        'rootfs', help="rootfs to operate on")
    ap.add_argument(
        '--source', help="local or remote path to dir or tarball to copy to "
        "Linux_for_Tegra/rootfs (specify 'l4t' or 'ubuntu_base' to download "
        "a new rootfs from nvidia (l4t) or Canonical (Ubuntu Base)",)
    ap.add_argument(
        '--source-sha512', help="if specifying a url, verifies the download with "
        "this sha512 hexdigest")
    ap.add_argument(
        '--apply-binaries', help="runs apply_binaries.sh", action='store_true',
        dest='do_apply_binaries')
    ap.add_argument(
        '--target-overlay', help="option for apply_binaries.sh (use if you've "
        "customized your kernel)", action='store_true')
    ap.add_argument(
        '--fix-sources', help="patches nvidia apt source.list so updates work "
        "before first boot.", action='store_true')

    main(**tegrity.cli.cli_common(ap))


if __name__ == '__main__':
    cli_main()
