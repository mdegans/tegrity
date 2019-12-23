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
import time
import math

import tegrity

NANO_SD_CARD_SCRIPT = "create-jetson-nano-sd-card-image.sh"
JETSON_DISK_IMAGE_CREATOR = ("tools", "jetson-disk-image-creator.sh")

logger = logging.getLogger(__name__)


# todo: change this when adding Xavier support
def make_image(l4t_path: os.PathLike,
               out: os.PathLike = None,):
    """
    Make OS Image for Tegra.

    if Nano, it creates a SD card
    Xavier support planned.

    :param l4t_path: the path to a Linux_for_Tegra folder
    :param hwid: the hardware id of the board (eg. P3448-0000)
    :param out: the out path for the disk image
    :return:
    """
    # todo: add xavier support. Thanks Nvidia!
    # todo: refactor, this is too long and ugly
    hwid = tegrity.db.autodetect_hwid(l4t_path)
    if hwid == tegrity.db.NANO_DEV_ID:
        if not out:
            out = os.path.join(l4t_path, f"sdcard.{int(time.time())}.img")

        rootfs_size = tegrity.utils.estimate_size(
            os.path.join(l4t_path, 'rootfs'))
        # add 1GB for other partitions, updates, some guaranteed free space,
        # and round up to nearest power of two sd card size:
        sd_size = 2 ** (math.ceil(math.log(rootfs_size + 1, 2)))
        logger.info(f"a {sd_size} GB size SD card will be required.")

        old_script = os.path.join(l4t_path, NANO_SD_CARD_SCRIPT)
        new_script = os.path.join(l4t_path, *JETSON_DISK_IMAGE_CREATOR)
        arguments = [
            '-o', out,
            '-s', f"{sd_size}GB",
            '-r', '200',
        ]
        if os.path.isfile(old_script):
            script = old_script
        elif os.path.isfile(new_script):
            script = new_script
            arguments.extend(('-b', 'jetson-nano',))
        else:
            # todo: consider including and modifying jetson-disk-image-creator
            raise FileNotFoundError(
                f"could not find {NANO_SD_CARD_SCRIPT}, "
                f"or {os.path.join(*JETSON_DISK_IMAGE_CREATOR)} in "
                f"{l4t_path}.")
    else:
        raise NotImplemented(
            "only Jetson Nano Development version implemented so far")

    logger.info(
        f"Creating image for {tegrity.db.MODEL_NAME_MAP[hwid]} ({hwid})")
    tegrity.utils.run((script, *arguments)).check_returncode()
    logger.info(
        f"Your image for {tegrity.db.MODEL_NAME_MAP[hwid]} is located at: {out}")

    return out


def cli_main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Makes a Tegra disk image (currently only Nano Development)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,)

    ap.add_argument(
        'l4t_path', help="path to Linux_for_Tegra folder to search for kernel, "
        "rootfs, etc...",)

    ap.add_argument(
        '-o', '--out', help="out file for the image (default "
        "sdcard.{timestamp}.img in the Linux_for_Tegra folder)")

    make_image(**tegrity.cli.cli_common(ap))
