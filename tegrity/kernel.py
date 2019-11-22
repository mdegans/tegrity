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
import tempfile
import time

import tegrity

logger = logging.getLogger(__name__)

KERNEL_PATH = ('kernel', 'kernel-4.9')
DEFAULT_LOCALVERSION = '-tegrity'

NANO_TX1_URL = "https://developer.nvidia.com/embedded/dlc/r32-2-1_Release_v1.0/Nano-TX1/sources/public_sources.tbz2"
NANO_TX1_SHA = "c2609cd107989a89063aa21cf6e06c75fed1c3873e5ef5840d2eb297af30e8db00d23465484bc3c8669059ce48d62dfd68ea9a3e3a9ade5d9ab917a6d533a808"

XAVIER_TX2_URL = "https://developer.nvidia.com/embedded/dlc/r32-2-1_Release_v1.0/TX2-AGX/sources/public_sources.tbz2"
XAVIER_TX2_SHA = "697e191e4c546e39cd40d142404606099c82df909e2ffb5235d3e71ad2d9f07889c38c11468e439e1900850945353ec58b67ddbff5713256f176e07d55114f10"


def download_source(bundle: sqlite3.Row, source_dir):
    """
    gets kernel source

    :param bundle: tag to get (use list_tags() for a list of supported tags)
    :param source_dir: the directory to download sources to

    :raises: subprocess.CalledProcessError on error
    """
    logger.info("Obtaining kernel sources from tarball.")

    # choose the appropriate source tarball
    hwid = bundle['targetHW']
    if hwid in tegrity.rootfs.NANO_TX1_IDS:
        logger.debug("Selecting tarball for Nano/TX1")
        url = NANO_TX1_URL
        sha = NANO_TX1_SHA
    elif hwid in tegrity.rootfs.XAVIER_TX2_IDS:
        logger.debug("Selecting tarball for TX2/Xavier")
        url = XAVIER_TX2_URL
        sha = XAVIER_TX2_SHA
    else:
        raise ValueError(
            f"Unrecognized Hardware ID ({hwid}). Please report this.")

    with tempfile.TemporaryDirectory() as tmp:
        tegrity.download.extract(
            url, tmp,
            hasher=hashlib.sha512,
            hexdigest=sha
        )
        kernel_tarball = os.path.join(
            tmp, 'public_sources', 'kernel_src.tbz2')
        tegrity.download.extract(kernel_tarball, source_dir)


# this is following the instructions from:
# https://docs.nvidia.com/jetson/l4t/index.html#page/Tegra%2520Linux%2520Driver%2520Package%2520Development%2520Guide%2Fkernel_custom.html%23
def build(bundle: sqlite3.Row, cross_prefix,
          menuconfig=None,
          localversion=None,
          save_kconfig=None,
          load_kconfig=None):
    logger.info("Preparing to build kernel...")
    arch = "arm64"

    # TODO: refactor - this function is too long and hard to test

    # set up some initial paths
    l4t_path = tegrity.db.get_l4t_path(bundle)
    logger.debug(f"Linux_for_Tegra path: {l4t_path}")
    l4t_kernel_path = tegrity.utils.join_and_check(l4t_path, "kernel")
    logger.debug(f"L4T kernel path: {l4t_kernel_path}")
    with tempfile.TemporaryDirectory() as tmp:
        # set up a temporary rootfs folder instead of a real one just to create
        # the kernel_supplements which will be installed by apply_binaries.sh
        temp_rootfs = os.path.join(tmp, 'rootfs')
        logger.debug(f"creating temporary rootfs at: {temp_rootfs}")
        os.makedirs(temp_rootfs, 0o755)

        ## Obtaining the Kernel Sources

        source_path = os.path.join(tmp, 'sources')
        logger.debug(f"source path: {source_path}")
        os.mkdir(source_path, mode=0o755)
        download_source(bundle, source_path)
        kernel_source_path = os.path.join(source_path, *KERNEL_PATH)
        if not os.path.isdir(kernel_source_path):
            raise RuntimeError(
                "Could not find kernel source. "
                "Change KERNEL_PATH to match git in kernel.py maybe?")
        os.chdir(kernel_source_path)

        ## Building the kernel

        # 1. set kernel out path
        kernel_out = os.path.join(tmp, "kernel_out")

        # 2. set CROSS_COMPILE and LOCALVERSION
        os.environ['CROSS_COMPILE'] = cross_prefix
        logger.debug(f'CROSS_COMPILE: {cross_prefix}')
        localversion = localversion if localversion else DEFAULT_LOCALVERSION
        os.environ['LOCALVERSION'] = localversion
        logger.debug(f'LOCALVERSION: {localversion}')

        # 2.5 set common make arguments
        make_common = [f"ARCH={arch}", f"O={kernel_out}"]

        # 3. Create the initial config
        logger.info("Configuring kernel")
        os.mkdir(kernel_out, 0o755)
        if load_kconfig:
            config_filename = os.path.join(kernel_source_path, '.config')
            tegrity.utils.backup(config_filename)
            tegrity.utils.copy(load_kconfig, config_filename)
        else:
            # use the default config
            tegrity.utils.run(
                ("make", *make_common, "tegra_defconfig"),
            ).check_returncode()
        os.chdir(kernel_out)

        # 3.5 Customize initial configuration interactively (optional)
        if menuconfig:
            tegrity.utils.run(
                ("make", *make_common, "menuconfig"),
            ).check_returncode()

        # 4 Build the kernel and all modules
        jobs = os.cpu_count()
        logger.info(f"Building the kernel using all available cores ({jobs}).")
        tegrity.utils.run(
            ("make", *make_common, f"-j{jobs}")
        ).check_returncode()

        # 5 Backup and replace old kernel with new kernel
        logger.info("Replacing old kernel")
        timestamp = int(time.time())
        new_kernel = os.path.join(
            kernel_out, "arch", "arm64", "boot", "Image")
        if not os.path.isfile(new_kernel):
            errmsg = f"Can't find new kernel at {new_kernel}."
            input(f"{errmsg} press enter to quit. debug: tmp:{tmp}")
            raise RuntimeError(errmsg)
        old_kernel = os.path.join(l4t_kernel_path, "Image")
        if not os.path.isfile(old_kernel):
            logger.warning(f"Old kernel not found at {old_kernel}")
        else:
            backup_image = os.path.join(
                l4t_kernel_path, f"Image.tegrity.backup.{timestamp}")
            os.rename(old_kernel, backup_image)
            logger.info(f"Old kernel backed up to {backup_image}")
        os.rename(new_kernel, old_kernel)

        # 6 Replace dtb folder with dts folder
        logger.info("Replacing old dtb folder.")
        new_dtb = os.path.join(
            kernel_out, "arch", "arm64", "boot", "dts")
        if not os.path.isdir(new_dtb):
            raise RuntimeError("Can't find new dtb folder.")
        old_dtb = os.path.join(l4t_kernel_path, "dtb")
        if not os.path.isdir(old_dtb):
            logger.warning(f"Old dtb not found at {old_dtb}")
        else:
            backup_dtb = os.path.join(
                l4t_kernel_path, f"dtb.tegrity.backup.{timestamp}")
            os.rename(old_dtb, backup_dtb)
            logger.info(f"Old dtb folder backed up to {old_dtb}")
        os.rename(new_dtb, old_dtb)

        # 7 Install kernel modules
        logger.info("Installing kernel modules to temporary rootfs.")
        tegrity.utils.run(
            ("make", *make_common, "modules_install",
             f"INSTALL_MOD_PATH={temp_rootfs}")
        )

        # 8 Archive modules
        module_archive = os.path.join(
            l4t_kernel_path, "kernel_supplements.tbz2")
        if os.path.isfile(module_archive):
            logger.info("Backing up old kernel supplements")
            os.rename(
                module_archive, f"{module_archive}.tegrity.backup.{timestamp}")
        os.chdir(temp_rootfs)
        logger.info(f"Archiving modules as {module_archive}")
        tegrity.utils.run(
            ("tar", "--owner", "root", "-cjf", module_archive, "lib/modules"),
        ).check_returncode()

        # 8.5 Archive config
        if save_kconfig:
            used_config = os.path.join(kernel_out, '.config')
            if os.path.exists(save_kconfig):
                tegrity.utils.backup(save_kconfig)
            tegrity.utils.copy(used_config, save_kconfig)

    # todo: backup kernel configuration
    # todo: support for external kernel modules:


