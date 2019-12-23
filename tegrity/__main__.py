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

import os
import logging

from typing import (
    Iterable,
)

import tegrity
import tegrity.settings

logger = logging.getLogger(__name__)


def build(l4t_path: os.PathLike,
          cross_prefix: str = None,
          firstboot: Iterable[os.PathLike] = None,
          build_kernel: bool = False,
          kernel_load_config: os.PathLike = None,
          kernel_save_config: os.PathLike = None,
          kernel_menuconfig: bool = None,
          kernel_localversion: str = None,
          public_sources: str = None,
          public_sources_sha512: str = None,
          rootfs_source: str = None,
          rootfs_source_sha512: str = None,
          out: str = None,):

    # if not l4t_path and hwid, prompt the user to choose a bundle with that
    # info from ~/.nvsdkm/sdkm.db
    rootfs = tegrity.utils.join_and_check(l4t_path, 'rootfs')

    # build the kernel (see kernel.py), modules, etc...
    if build_kernel:
        tegrity.kernel.build(
            l4t_path, public_sources,
            cross_prefix=cross_prefix,
            public_sources_sha512=public_sources_sha512,
            menuconfig=kernel_menuconfig,
            localversion=kernel_localversion,
            save_kconfig=kernel_save_config,
            load_kconfig=kernel_load_config,)

    tegrity.rootfs.main(
        rootfs,
        rootfs_source,
        rootfs_source_sha512,
        do_apply_binaries=build_kernel or rootfs_source,
        target_overlay=build_kernel,
        fix_sources=rootfs_source,
    )

    # install any first boot scripts
    if firstboot:
        tegrity.firstboot.install_first_boot_scripts(
            rootfs, firstboot, overwrite=True, interactive=True,)

    # assemble the final image(s)
    return tegrity.image.make_image(l4t_path, out=out)


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Helps bake Tegra OS images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,)

    chooser_msg = "(**required to avoid interactive chooser**)"

    # l4t_path: os.PathLike = None,
    ap.add_argument(
        'l4t_path', help=f"path to desired Linux_for_Tegra path.")
    # cross_prefix: str = None,
    ap.add_argument(
        '--cross-prefix', help="the default cross prefix",
        default=tegrity.toolchain.get_cross_prefix())
    # firstboot: Iterable[os.PathLike] = None,
    ap.add_argument(
        '--firstboot', help="list of first boot scripts to install", nargs='+',)
    # public_sources: str = None,
    ap.add_argument(
        '--public-sources', help="url or local path to a public sources tarball.",
        default=tegrity.settings.NANO_TX1_KERNEL_URL,)
    # public_sources_sha512: str = None,
    ap.add_argument(
        '--public-sources-sha512', help="public sources sha512 expected",
        default=tegrity.settings.NANO_TX1_KERNEL_SHA512,)
    # build_kernel: bool = False,
    ap.add_argument(
        '--build-kernel', help="builds the kernel", action='store_true')
    # kernel_load_config: os.PathLike = None,
    ap.add_argument(
        '--kernel-load-config', help="loads kernel configuration from this file")
    # kernel_save_config: os.PathLike = None,
    ap.add_argument(
        '--kernel-save-config', help="save kernel configuration to this file")
    # kernel_localversion: str = None,
    ap.add_argument(
        '--kernel-localversion', help="local version string for kernel",
        default=tegrity.settings.DEFAULT_LOCALVERSION,)
    # kernel_menuconfig: bool = None,
    ap.add_argument(
        '--kernel-menuconfig', help="interactively configure kernel",
        action='store_true',)
    # rootfs_source: str = None,
    ap.add_argument(
        '--rootfs-source', help='url or local path to rootfs tarball / directory, '
        'specify "l4t" to download a new default rootfs, or "ubuntu_base" to get '
        'an Ubuntu Base rootfs.')
    # rootfs_sources_sha512: str = None,
    ap.add_argument(
        '--rootfs-source-sha512', help='sha512sum of rootfs tarball')
    # out: str = None, ):
    ap.add_argument(
        '-o', '--out', help="the out path (for sd card image, etc)")

    kwargs = tegrity.cli.cli_common(ap)

    return build(**kwargs)


if __name__ == '__main__':
    cli_main()
