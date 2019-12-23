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
import platform
import shutil
import subprocess
import tempfile
import urllib.request

import tegrity

from typing import (
    Optional,
)

logger = logging.getLogger(__name__)

# toolchain minimum version needed
MINIMUM_VERSION = "7.3.1"

# used to find the toolchain binaries, no need to change this on Tegra,
# but could be used if this script is ported to x86
ARCH = 'aarch64'

DEFAULT_TARBALL_INSTALL_PREFIX = '/usr/local'

if platform.machine() == "i386":
    URL = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-i686_aarch64-linux-gnu.tar.xz"
    MD5 = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-i686_aarch64-linux-gnu.tar.xz.asc"
elif platform.machine() == "x86_64":
    URL = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-x86_64_aarch64-linux-gnu.tar.xz"
    MD5 = "https://releases.linaro.org/components/toolchain/binaries/7.3-2018.05/aarch64-linux-gnu/gcc-linaro-7.3.1-2018.05-x86_64_aarch64-linux-gnu.tar.xz.asc"
else:
    raise RuntimeError(
        "Unsupported architecture. Only x86 and x86-64 currently supported.")


def get_cross_prefix() -> Optional[str]:
    """:returns: the cross prefix for the toolchain in path"""
    logger.debug(f"Checking for cross compiler...")
    gcc = shutil.which(f"aarch64-linux-gnu-gcc")
    if not gcc:
        return
    logger.debug(f"Found gcc cross compiler at {gcc}")
    cross_prefix = os.path.join(
        os.path.dirname(shutil.which(f"aarch64-linux-gnu-gcc")),
        f"aarch64-linux-gnu-")
    return cross_prefix


# noinspection PyUnresolvedReferences
def install_from_tarball(
        install_path: os.PathLike = DEFAULT_TARBALL_INSTALL_PREFIX) -> str:
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


def ensure(cross_prefix=None) -> str:
    """ensures toolchain is installed interactively and returns cross prefix

    :param cross_prefix: overrides auto-detection, still checks if gcc exists

    >>> ensure()
    '/usr/local/bin/aarch64-linux-gnu-'
    """
    # autodetect cross_prefix if not supplied
    cross_prefix = cross_prefix if cross_prefix else get_cross_prefix()
    # this should point to gcc:
    gcc = f"{cross_prefix}gcc"
    if cross_prefix and os.path.isfile(gcc):
        return cross_prefix
    else:
        logger.error(
            "aarch64-linux-gnu toolchain not found. Do you wish to install "
            "one, either from system apt repositories or the recommended from "
            "releases.linaro.org?"
        )
        choice = None
        while not 1 <= choice <= 2:
            try:
                choice = int(input(
                    "choose 1 (apt), 2 (releases.linaro.org), or ctrl+c to exit")
                )
            except ValueError:
                logger.error("invalid choice, try again")
                pass
        if choice == 1:
            return tegrity.toolchain.install_from_apt()
        elif choice == 2:
            return tegrity.toolchain.install_from_tarball()


def main(check=None,
         install_tarball=None,
         prefix=None,
         install_apt=None):
    if not (check or install_tarball or install_apt):
        raise ValueError("Nothing to do.")
    cross_prefix = get_cross_prefix()
    if check:
        if not cross_prefix:
            raise FileNotFoundError("Toolchain not found.")
    if install_tarball:
        cross_prefix = install_from_tarball(prefix)
    if install_apt:
        cross_prefix = install_from_apt()
    logger.info(f"CROSS_PREFIX={cross_prefix}")


def cli_main():
    import argparse
    ap = argparse.ArgumentParser(
        description='toolchain utility',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ap.add_argument(
        '--check', help="checks if the toolchain meets requirements",
        action='store_true'),
    ap.add_argument(
        '--install-tarball', help="downloads and installs NVIDIA recommended"
        "linaro toolchain",
        action='store_true'),
    ap.add_argument(
        '--prefix', help="install prefix for recommended linaro tarball",
        default='/usr/local'),
    ap.add_argument(
        '--install-apt', help="install distro bundled toolchain (not "
        "recommended, but it appears to work)",
        action='store_true'),

    # add --log-file and --verbose
    main(**tegrity.cli.cli_common(ap))


if __name__ == '__main__':
    cli_main()
