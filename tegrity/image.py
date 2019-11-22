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
import sqlite3
import time
import math

import tegrity

NANO_SD_CARD_SCRIPT = "create-jetson-nano-sd-card-image.sh"

logger = logging.getLogger(__name__)


def make_image(bundle: sqlite3.Row,
               image_out_path=None,):
    """
    Make OS Image for Tegra.

    If Xavier, it creates a flashable xavier image
    if Nano, it creates a SD card

    :param bundle:
    :param image_out_path:
    :return:
    """
    l4t = tegrity.db.get_l4t_path(bundle)
    hwid = bundle['targetHW']

    # jetson nano development kit
    if hwid in tegrity.db.NANO_IDS:
        if not image_out_path:
            image_out_path = os.path.join(l4t, f"sdcard.{int(time.time())}.img")

        rootfs_size = tegrity.utils.estimate_size(os.path.join(l4t, 'rootfs'))
        # add 1GB for other partitions, updates, some guaranteed free space,
        # and round up to nearest power of two sd card size:
        sd_size = 2 ** (math.ceil(math.log(rootfs_size + 1, 2)))
        logger.info(f"a {sd_size}GB size SD card will be required.")

        script = os.path.join(l4t, NANO_SD_CARD_SCRIPT)
        arguments = (
            '-o', image_out_path,
            '-s', f"{sd_size}GB",
            '-r', '200' if hwid == tegrity.db.NANO_DEV_ID else '300',
        )
    else:
        raise NotImplemented("only Jetson Nano implemented so far")

    logger.info(
        f"Creating image for {tegrity.db.MODEL_NAME_MAP[hwid]} ({hwid})")
    tegrity.utils.run((script, *arguments), cwd=l4t).check_returncode()
    logger.info(f"Your image for {tegrity.db.MODEL_NAME_MAP[hwid]} "
                f"is located at: {image_out_path}")

