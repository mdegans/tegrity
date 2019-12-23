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
import tempfile

import tegrity

from typing import (
    Iterable,
)

from tegrity.settings import (
    KERNEL_TARBALL_PATH,
    KERNEL_PATH,
    DEFAULT_LOCALVERSION,
    NANO_TX1_KERNEL_URL,
    NANO_TX1_KERNEL_SHA512,
)

logger = logging.getLogger(__name__)

# this should never need to change on Tegra, but if you want to use this code
# elsewhere, it might be useful (tells make which architecture ot target)
ARCH = 'arm64'


def _get_source(tmp, public_sources, public_sources_sha):
    """called from main, separated for testing purposes"""
    source_path = os.path.join(tmp, 'sources')
    logger.debug(f"source path: {source_path}")
    os.mkdir(source_path, mode=0o755)
    download_source(
        public_sources, source_path,
        hasher=hashlib.sha512,
        hexdigest=public_sources_sha, )
    kernel_source_path = os.path.join(source_path, *KERNEL_PATH)
    if not os.path.isdir(kernel_source_path):
        raise RuntimeError("Could not find kernel source.")
    os.chdir(kernel_source_path)


def download_source(public_sources: str, source_dir,
                    hasher=None,
                    hexdigest=None):
    """
    gets kernel source

    :param public_sources: url or path to public_sources.tbz2
    :param source_dir: the directory to download sources to
    :param hasher: passed to tegrity.download.extract to verify
    public_sources.tbz2
    :param hexdigest: passed to tegrity.download.extract to verify
    public_sources.tbz2
    """
    logger.info(f"Obtaining kernel sources from {public_sources}.")
    with tempfile.TemporaryDirectory() as tmp:
        tegrity.download.extract(
            public_sources, tmp, hasher=hasher, hexdigest=hexdigest)
        kernel_tarball = os.path.join(
            tmp, *KERNEL_TARBALL_PATH)
        try:
            tegrity.download.extract(kernel_tarball, source_dir)
        except FileNotFoundError as err:
            raise FileNotFoundError(
                f"{err.filename} not found in tarball. Bad url?"
            )


# this is following the instructions from:
# https://docs.nvidia.com/jetson/l4t/index.html#page/Tegra%2520Linux%2520Driver%2520Package%2520Development%2520Guide%2Fkernel_custom.html%23
def build(l4t_path, public_sources,
          # todo: xconfig=None,
          arch=ARCH,
          cross_prefix=tegrity.toolchain.get_cross_prefix(),
          load_kconfig=None,
          localversion=None,
          menuconfig=None,
          module_archive=None,
          public_sources_sha512=None,
          save_kconfig=None,
          ):

    logger.info("Preparing to build kernel")

    # set some envs
    os.environ['CROSS_COMPILE'] = cross_prefix
    logger.debug(f'CROSS_COMPILE: {cross_prefix}')
    localversion = localversion if localversion else DEFAULT_LOCALVERSION
    os.environ['LOCALVERSION'] = localversion
    logger.debug(f'LOCALVERSION: {localversion}')

    # set up some initial paths
    logger.debug(f"Linux_for_Tegra path: {l4t_path}")
    l4t_kernel_path = tegrity.utils.join_and_check(l4t_path, "kernel")
    logger.debug(f"L4T kernel path: {l4t_kernel_path}")

    # create a temporary folder that self destructs at the end of the context.
    with tempfile.TemporaryDirectory() as tmp:

        # set up a temporary rootfs folder instead of a real one just to create
        # the kernel_supplements which will be installed by apply_binaries.sh
        rootfs = os.path.join(tmp, 'rootfs')
        logger.debug(f"creating temporary rootfs at: {rootfs}")
        os.makedirs(rootfs, 0o755)

        # Obtaining the Kernel Sources
        _get_source(tmp, public_sources, public_sources_sha512)

        # Building the kernel

        # 1. set kernel out path
        kernel_out = os.path.join(tmp, "kernel_out")

        # 2.5 set common make arguments
        make_common = [f"ARCH={arch}", f"O={kernel_out}"]

        # 3. Create the initial config
        config(make_common, kernel_out, load_kconfig)
        os.chdir(kernel_out)

        # 3.5 Customize initial configuration interactively (optional)
        if menuconfig:
            make_menuconfig(make_common)

        # 4 Build the kernel and all modules
        make_kernel(make_common)

        # 5 Backup and replace old kernel with new kernel
        replace_kernel(kernel_out, l4t_kernel_path)

        # 6 Replace dtb folder with dts folder
        replace_dtb(kernel_out, l4t_kernel_path)

        # 7 Install kernel modules
        make_modules_install(make_common, rootfs)

        # 8 Archive modules
        archive_modules(rootfs, module_archive, l4t_kernel_path)

        # 8.5 Archive config
        archive_kconfig(kernel_out, save_kconfig)

    # todo: support for external kernel modules:


def config(make_args, kernel_out,
           load_kconfig=None,
           kernel_source_path=None):
    logger.info("Configuring kernel")
    os.mkdir(kernel_out, 0o755)
    if load_kconfig:
        config_filename = os.path.join(kernel_source_path, '.config')
        tegrity.utils.copy(load_kconfig, config_filename)
    else:
        # use the default config
        tegrity.utils.run(
            ("make", *make_args, "tegra_defconfig"),
        ).check_returncode()


def make_menuconfig(make_args: Iterable):
    tegrity.utils.run(
        ("make", *make_args, "menuconfig"),
    ).check_returncode()


def make_kernel(make_args: Iterable):
    jobs = os.cpu_count()
    logger.info(f"Building the kernel using all available cores ({jobs}).")
    tegrity.utils.run(
        ("make", *make_args, f"-j{jobs}")
    ).check_returncode()


def replace_kernel(kernel_out, l4t_kernel_path):
    logger.info("Replacing old kernel")
    new_kernel = os.path.join(
        kernel_out, "arch", "arm64", "boot", "Image")
    if not os.path.isfile(new_kernel):
        raise RuntimeError(f"Can't find new kernel at {new_kernel}.")
    old_kernel = os.path.join(l4t_kernel_path, "Image")
    if os.path.exists(old_kernel):
        tegrity.utils.backup(old_kernel)
    tegrity.utils.move(new_kernel, old_kernel)


def replace_dtb(kernel_out, l4t_kernel_path):
    logger.info("Replacing old dtb folder.")
    new_dtb = os.path.join(
        kernel_out, "arch", "arm64", "boot", "dts")
    if not os.path.isdir(new_dtb):
        raise RuntimeError("Can't find new dtb folder.")
    old_dtb = os.path.join(l4t_kernel_path, "dtb")
    if os.path.exists(old_dtb):
        tegrity.utils.backup(old_dtb)
    tegrity.utils.move(new_dtb, old_dtb)


def make_modules_install(make_args: Iterable, rootfs):
    logger.info("Installing kernel modules to temporary rootfs.")
    tegrity.utils.run(
        ("make", *make_args, "modules_install",
         f"INSTALL_MOD_PATH={rootfs}")
    )


def archive_modules(rootfs, module_archive=None, l4t_kernel_path=None):
    if not module_archive:
        if l4t_kernel_path:
            module_archive = os.path.join(
                l4t_kernel_path, "kernel_supplements.tbz2")
        else:
            raise ValueError("module_archive or l4t_kernel_path required")
    if os.path.isfile(module_archive):
        logger.info("Backing up old kernel supplements")
        tegrity.utils.backup(module_archive)
    os.chdir(rootfs)
    logger.info(f"Archiving modules as {module_archive}")
    tegrity.utils.run(
        ("tar", "--owner", "root", "-cjf", module_archive, "lib/modules"),
    ).check_returncode()


def archive_kconfig(kernel_out_folder, config_out):
    if config_out:
        used_config = os.path.join(kernel_out_folder, '.config')
        if os.path.exists(config_out):
            tegrity.utils.backup(config_out)
        tegrity.utils.move(used_config, config_out)


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description='kernel building tool',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        'l4t_path', help="the path to the Linux_for_Tegra folder to operate on")
    ap.add_argument(
        '--cross-prefix', help='sets the CROSS_PREFIX variable',
        default=tegrity.toolchain.get_cross_prefix())
    ap.add_argument(
        '--public_sources', help="a local or remote path to a nvidia public_sources"
        "tarball.", default=NANO_TX1_KERNEL_URL)
    ap.add_argument(
        '--public_sources_sha', help="the expected sha512 sum of the tarball",
        default=NANO_TX1_KERNEL_SHA512)
    ap.add_argument(
        '--localversion', help="kernel name suffix",
        default=DEFAULT_LOCALVERSION)
    ap.add_argument('--save-kconfig', help="save kernel config to this file")
    ap.add_argument('--load-kconfig', help="load kernel config from this file")
    ap.add_argument(
        '--menuconfig', help="customize kernel config interactively using a menu "
        "(WARNING: here be dragons! While it's unlikely, you could possibly "
        "damage your Tegra or connected devices if the kernel is "
        "mis-configured).", action='store_true')

    # add --log-file and --verbose
    build(**tegrity.cli.cli_common(ap))


if __name__ == '__main__':
    cli_main()
