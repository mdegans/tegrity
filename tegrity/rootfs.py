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

import tegrity

# urls, shas, and supported model numbers for their rootfs'
# please customize these if they are outdated.
# new sha512 sums can be generated with python's hashlib module or
# the sha512sum command
XAVIER_TX2_URL = "https://developer.nvidia.com/embedded/dlc/r32-2-1_Release_v1.0/TX2-AGX/Tegra_Linux_Sample-Root-Filesystem_R32.2.1_aarch64.tbz2"
XAVIER_TX2_SHA = "bb2c6fb38052549e95b5b5d68298295b757e13f608d0260a405c9a45567b6eaf38fd11c526a5a4655e1cda0cbe0056f98c34ddc6c2efa1baf1376fe49ff39e4b"
XAVIER_TX2_IDS = {tegrity.db.TX2_ID, tegrity.db.XAVIER_ID}
NANO_TX1_URL = "https://developer.nvidia.com/embedded/dlc/r32-2-1_Release_v1.0/Nano-TX1/Tegra_Linux_Sample-Root-Filesystem_R32.2.1_aarch64.tbz2"
NANO_TX1_SHA = "bb2c6fb38052549e95b5b5d68298295b757e13f608d0260a405c9a45567b6eaf38fd11c526a5a4655e1cda0cbe0056f98c34ddc6c2efa1baf1376fe49ff39e4b"
NANO_TX1_IDS = {tegrity.db.TX1_ID, *tegrity.db.NANO_IDS}

logger = logging.getLogger(__name__)


def get_path(bundle: sqlite3.Row):
    """:returns: the path to the rootfs of the |bundle|"""
    l4t_path = tegrity.db.get_l4t_path(bundle)
    return tegrity.utils.join_and_check(l4t_path, "rootfs")


def reset(bundle: sqlite3.Row, source=None) -> str:
    """resets a rootfs for a |bundle| to stock, backing up the old one"""
    logger.info(f"resetting rootfs{' from ' + source if source else ''}")
    rootfs = get_path(bundle)
    if source:
        # download, extract, or copy it
        if type(source) is str and source.startswith("http"):
            if not source.startswith("https"):
                logger.warning(f"{source} is a http url. changing to https")
                source = f"https{source[4:]}"
            tegrity.utils.backup(rootfs)
            tegrity.download.extract(source, rootfs)
        if os.path.isfile(source):
            tegrity.utils.backup(rootfs)
            tegrity.download.extract(source, rootfs)
        if os.path.isdir(source):
            if not os.path.exists(os.path.join(source, 'etc')):
                raise tegrity.err.InSanityError(
                    "/etc/ not found. This doesn't look like a rootfs"
                )
            tegrity.utils.backup(rootfs)
            tegrity.utils.copy(source, rootfs)
        return rootfs
    # else, download and verify a new copy
    hwid = bundle['targetHW']
    if hwid in XAVIER_TX2_IDS:
        url = XAVIER_TX2_URL
        sha = XAVIER_TX2_SHA
    elif hwid in NANO_TX1_IDS:
        url = NANO_TX1_URL
        sha = NANO_TX1_SHA
    else:
        raise ValueError(f"{hwid} not recognized as hardware id")
    tegrity.utils.backup(rootfs)
    tegrity.download.extract(
        url, rootfs,
        hasher=hashlib.sha512,
        hexdigest=sha,
    )
    return rootfs


def apply_binaries(bundle: sqlite3.Row,):
    """runs the apply_binaries.sh script for a selected bundle"""
    l4t_path = tegrity.db.get_l4t_path(bundle)
    rootfs = get_path(bundle)
    script = tegrity.utils.join_and_check(l4t_path, 'apply_binaries.sh')
    command = (script, '-r', rootfs)
    tegrity.utils.run(command, cwd=l4t_path).check_returncode()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    import doctest
    doctest.testmod()
