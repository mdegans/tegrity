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

__version__ = '0.0.3'

import logging

import tegrity.db
from tegrity.settings import (
    CONFIG_PATH_MODE,
    DEFAULT_CONFIG_PATH,
)
import tegrity.cli
import tegrity.download
import tegrity.err
import tegrity.firstboot
import tegrity.image
import tegrity.toolchain
import tegrity.kernel
import tegrity.qemu
import tegrity.apt
import tegrity.rootfs
import tegrity.service
import tegrity.utils

logger = logging.getLogger(__name__)

try:
    # noinspection PyUnresolvedReferences
    import tegrity.gui
except ImportError as err:
    tegrity.gui = None
    if err.name == 'gi':
        logger.debug(
            "gi not available, so tegrity.gui = None and --gui cannot be used."
            "try: sudo apt install python3-gi")
    else:
        raise
