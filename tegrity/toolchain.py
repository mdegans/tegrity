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

import distutils.version
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request

import tegrity

from typing import (
    Optional,
    Union,
)

logger = logging.getLogger(__name__)

MINIMUM_VERSION = "7.3.1"

if platform.machine() == "i386":
    URL = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-i686_aarch64-linux-gnu.tar.xz"
    MD5 = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-i686_aarch64-linux-gnu.tar.xz.asc"
elif platform.machine() == "x86_64":
    URL = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-x86_64_aarch64-linux-gnu.tar.xz"
    MD5 = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-x86_64_aarch64-linux-gnu.tar.xz.asc"
else:
    raise RuntimeError(
        "Unsupported architecture. Only x86 and x86-64 currently supported.")


def get_cross_version() -> Optional[str]:
    """Checks the cross compiler version (technically just checks gcc version).
    :returns: None if none found or the strict version string if found
    >>> get_cross_version()
    '7...'
    """
    logger.debug("Checking for gcc cross compiler...")
    gcc = shutil.which("aarch64-linux-gnu-gcc")
    if not gcc:
        return
    logger.debug(f"Found gcc cross compiler at {gcc}")
    cp = subprocess.run((gcc, '--version'), stdout=subprocess.PIPE)
    version_string = cp.stdout.splitlines()[0].split()[-1].decode()
    logger.debug(f"Version reported is {version_string}")
    return version_string


def has_valid_version() -> bool:
    """:returns: True if a supported version of gcc is found, False otherwise
    >>> has_valid_version()
    True
    """
    version = get_cross_version()
    if not version:
        return False
    min_version = distutils.version.StrictVersion(MINIMUM_VERSION)
    return distutils.version.StrictVersion(version) > min_version


# noinspection PyUnresolvedReferences
def install_from_tarball(install_path: Union[str, os.PathLike] = None) -> str:
    """
    Installs the cross compiler toolchain to |install_path| (default /usr/local)
    :returns: the cross prefix

    >>> logging.basicConfig(level=logging.DEBUG)
    >>> logger.debug("Testing install_from_tarball")
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     cross_prefix = install_from_tarball(tmp)
    ...     bindir = os.path.dirname(cross_prefix)
    ...     os.path.isfile(os.path.join(bindir, 'aarch64-linux-gnu-gcc'))
    True
    """
    if not install_path:
        install_path = "/usr/local"
    logger.debug(f"Install path set to: {install_path}")

    # get the md5 to verify archive tegrity
    with urllib.request.urlopen(MD5) as response:
        logger.debug(f"Fetching checksum from {MD5}")
        hexdigest = response.read(32).decode()
        logger.debug(f"got md5sum: {hexdigest}")

    with tempfile.TemporaryDirectory() as extract_dir:
        logger.info("Downloading and verifying toolchain...")
        member_list = tegrity.download.extract(
            URL, extract_dir,
            hasher=hashlib.md5,
            hexdigest=hexdigest,
        )
        # todo: this is a sloppy assumption that the tarball will always be this
        #  format, fix so it's more flexible for possible future changes.:
        if member_list[0].isdir():
            top_level_folder = member_list[0].name
        else:
            raise RuntimeError(
                f"Could not find top level folder in tarball. "
                f"{tegrity.err.TOOLCHAIN_TRY_APT}"
            )
        rsync_source = os.path.join(extract_dir, top_level_folder)
        logger.debug(f"rsync source: {rsync_source}")
        if not os.path.isdir(rsync_source):
            raise RuntimeError(
                f"Could not find extracted top level folder."
                f"{tegrity.err.TOOLCHAIN_TRY_APT}"
            )

        logger.info(f"Installing toolchain:")
        subprocess.run(
            ("rsync", "-a", "--info=progress2", f"{rsync_source}/", install_path)
        ).check_returncode()

    return os.path.join(install_path, "bin", "aarch64-linux-gnu-")


def install_from_apt():
    """
    Installs the Ubuntu/debian repository version of gcc
    """
    tegrity.apt.install(("gcc-aarch64-linux-gnu",))
    return "/usr/bin/aarch64-linux-gnu-"


def ensure():
    """ensures toolchain is installed and returns bin directory

    >>> ensure()
    '/usr/bin/aarch64-linux-gnu-'
    """
    if not tegrity.toolchain.has_valid_version():
        logger.error(
            "Valid cross compiler toolchain not found. Do you wish to install "
            "one, either from system apt repositories or the recommended from "
            "releases.linaro.org?"
        )
        choice = None
        while not 1 <= choice <= 2:
            try:
                choice = int(input("Choose 1 (apt), 2 (releases.linaro.org),"
                                   "or press ctrl+c to exit. "))
            except ValueError:
                logger.error("invalid choice, try again")
                pass
        if choice == 1:
            return tegrity.toolchain.install_from_apt()
        elif choice == 2:
            return tegrity.toolchain.install_from_tarball()
    else:
        return os.path.join(
            os.path.dirname(shutil.which("aarch64-linux-gnu-gcc")),
            "aarch64-linux-gnu-"
        )


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
