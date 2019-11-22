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

import tegrity

logger = logging.getLogger(__name__)

TEGRITY_CONFIG_PATH_MODE = 0o700
# change this if it conflicts with an existing ~/.tegrity folder you want to
# to keep
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), f".{tegrity.__name__}")


def ensure_config_path(path=DEFAULT_CONFIG_PATH, mode=TEGRITY_CONFIG_PATH_MODE):
    logger.info(f"Ensuring {DEFAULT_CONFIG_PATH} exists")
    if os.path.exists(path):
        if os.path.isdir(path):
            tegrity.utils.chmod(path, mode)
        else:
            raise FileExistsError(
                f"{path} is supposed to be a directory, please relocate this "
                f"file if not needed or modify {tegrity.__name__} source"
            )
        path_stat = os.stat(path)
        if not path_stat.st_gid == 0 and path_stat.st_gid == 0:
            logger.warning(
                f"{DEFAULT_CONFIG_PATH} does not appear to be owned by root. "
                f"This is fine, but please be aware that sometimes sensitive "
                f"information is dumped into log files.")

    else:
        tegrity.utils.mkdir(path, mode)


def ensure_system_requirements():
    """ensures system requirements are installed and returns cross prefix"""
    logger.info("Ensuring system requirements...")
    tegrity.utils.ensure_sudo()
    tegrity.apt.ensure_requirements()
    return tegrity.toolchain.ensure()


def main(
        firstboot=None,
        load_kconfig=None,
        localversion=None,
        menuconfig=None,
        rootfs_source=None,
        save_kconfig=None,
):
    cross_prefix = ensure_system_requirements()
    ensure_config_path()
    with tegrity.db.connect() as conn:
        # choose bundle and set up paths
        bundle = tegrity.utils.chooser(
            tegrity.db.get_bundles(conn), "bundles",
            formatter=tegrity.db.bundle_formatter)

        if bundle['targetHW'] not in tegrity.db.SUPPORTED_IDS:
            raise NotImplemented(
                f"Model not supported (yet). Supported models: "
                f"{tegrity.db.SUPPORTED_IDS}")

        # build the kernel (see kernel.py), modules, etc...
        tegrity.kernel.build(
            bundle, cross_prefix,
            menuconfig=menuconfig,
            localversion=localversion,
            save_kconfig=save_kconfig,
            load_kconfig=load_kconfig,
        )

        if rootfs_source:
            if rootfs_source == 'download':
                tegrity.rootfs.reset(bundle)
            else:
                tegrity.rootfs.reset(bundle, rootfs_source)

        # apply binaries to the rootfs (kernel modules, nvidia stuff)
        tegrity.rootfs.apply_binaries(bundle)

        if firstboot:
            tegrity.firstboot.install_first_boot_scripts(
                tegrity.rootfs.get_path(bundle), firstboot)

        tegrity.image.make_image(bundle)


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Helps bake Tegra OS images",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # ap.add_argument(
    #     '--kernel-source', help=f"path to a kernel tarball downloaded from "
    #                             f"{tegrity.kernel.NANO_TX1_URL}"
    # )
    ap.add_argument(
        '--localversion', default=tegrity.kernel.DEFAULT_LOCALVERSION,
        help="override local version string (kernel name suffix).",
    )
    ap.add_argument('--save-kconfig', help="save kernel config to this file")
    ap.add_argument('--load-kconfig', help="load kernel config from this file")
    ap.add_argument(
        '--menuconfig', help="customize kernel config interactively using a menu "
        "(WARNING: here be dragons! While it's unlikely, you could possibly "
        "damage your Tegra or connected devices if the kernel is "
        "mis-configured).", action='store_true'
    )
    ap.add_argument(
        '--rootfs-source', help="Location of rootfs to download/extract/copy "
        "from. may be a url, path to a tarball, or a local directory path "
        "specify 'download' to download a new, bundle appropriate, copy "
        "from Nvidia. No arguments will use the existing rootfs."
    )
    # todo:
    #  finish this wip in firstboot.sh
    # ap.add_argument(
    #     '--firstboot', help=f"Iterable of first boot scripts to install. They "
    #     f"will be copied to rootfs/etc/{tegrity.firstboot.SCRIPT_FOLDER_NAME} "
    #     f"and executed **in the order supplied here** on first boot."
    # )
    # todo: implement
    # ap.add_argument(
    #     '--firstboot-dpkg', help="A list of Debian packages to "
    #     "copy to the rootfs. See manual for wildcard examples. They will be "
    #     "installed in the order dpkg sees fit on first boot before --firstboot"
    # )
    # ap.add_argument(
    #     '--firstboot-apt-install', help="a set of apt packages to install on "
    #     "first boot. Order does not matter. This will be run after"
    #     "--firstboot-dpkg"
    # )
    ap.add_argument(
        '-l', '--log-file', help="where to store log file",
        default=os.path.join(DEFAULT_CONFIG_PATH, "tegrity.log")
    )
    ap.add_argument(
        '-v', '--verbose', help="prints DEBUG log level (DEBUG is logged anyway "
        "in the ", action='store_true'
    )

    # get argparse args in dict format
    kwargs = vars(ap.parse_args())

    # set up configuration path
    ensure_config_path()

    # configure logging
    fh = logging.FileHandler(kwargs['log_file'])
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s::%(levelname)s::%(name)s::%(message)s'))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter())
    ch.setLevel(logging.DEBUG if kwargs['verbose'] else logging.INFO)
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=(fh, ch),
    )
    del kwargs['verbose'], kwargs['log_file']

    main(**kwargs)


if __name__ == '__main__':
    cli_main()
