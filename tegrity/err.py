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

# todo: add more errors from random files to here, combine similar ones

# change this is you fork the project:
README = "https://github.com/mdegans/tegrity/blob/master/README.md"
ISSUE_URL = "https://github.com/mdegans/tegrity/issues"

__all__ = [
    'BUNDLE_REINSTALL',
    'InSanityError',
    'InTegrityError',
    'INVALID_NUMBER',
    'NO_SDKM',
    'TOOLCHAIN_TRY_APT',
]

NO_SDKM = "Is NVIDIA SDK Manager installed?"
BUNDLE_REINSTALL = "Please try reinstalling your target board's bundle with" \
                   " SDK Manager."
INVALID_NUMBER = "Please choose a valid number (or ctrl+c to exit)."
TOOLCHAIN_TRY_APT = "Please report and/or try installing toolchain using apt."


class InTegrityError(RuntimeError):
    """raised on hash verification fail"""


class InSanityError(RuntimeError):
    """raised when something might harm the host system or Tegra"""
