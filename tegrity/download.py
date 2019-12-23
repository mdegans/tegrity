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
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

from typing import (
    Any,
    Callable,
    List,
    Optional,
    Text,
    Union,
)

import tegrity
from tegrity.settings import LBZIP2

logger = logging.getLogger(__name__)

__all__ = [
    'download',
    'extract',
    'verify',
]


def download(url: Text,
             path: str,
             hexdigest: Optional[str] = None,
             hasher: Optional[Callable[[bytes], Any]] = None,
             chunk_size=2**20) -> Text:
    """
    Downloads a file at |url| to |path|.

    :arg url: as str, bytes
    :arg path: destination path. str, bytes, os.PathLike will all work

    :param hexdigest: Expected hash from hasher
    :param hasher: hasher to use (eg. "hashlib.md5" hashlib)
    :param chunk_size: chunk size (in bytes) to download in

    :return: destination filename
    """
    # todo: progress reporting
    url_path = urllib.parse.urlparse(url).path
    filename = os.path.basename(url_path)
    local_dest = os.path.join(path, filename)

    # download file in chunks while updating hasher
    logger.debug(f"Downloading {url} to {local_dest}")

    if hasher and hexdigest:
        hasher = hasher()
        logger.debug(f"Using {hasher.name} to verify download.")
        logger.debug(f"Expecting hex digest: {hexdigest}")

    with urllib.request.urlopen(url) as response, open(local_dest, 'wb') as f:
        chunk = response.read(chunk_size)
        while chunk:
            f.write(chunk)
            if hasher and hexdigest:
                hasher.update(chunk)
            chunk = response.read(chunk_size)

    # verify hasher result against
    if hasher and hexdigest:
        if hasher.hexdigest() != hexdigest:
            raise tegrity.err.InTegrityError(
                f"Hash verification failed for {url}. "
                f"expected: {hexdigest} but got {hasher.hexdigest()}"
            )

    return local_dest


# noinspection PyPep8Naming
def extract(file_or_url: str,
            path: str,
            hexdigest: Optional[str] = None,
            hasher: Optional[Callable] = None,
            **kwargs) -> Union[List[zipfile.ZipInfo], List[tarfile.TarInfo]]:
    """
    (Downloads) and extracts a file or url to path.

    :param file_or_url: file or url to extract
    :param path: path to extract to
    :param kwargs: passed to download()
    :param hexdigest: Expected hash from hasher
    :param hasher: hasher to use (eg. "hashlib.md5" hashlib)

    :returns: an archive file member list
    """

    if file_or_url.endswith('.zip'):
        ArkFile = zipfile.ZipFile
    elif file_or_url.endswith(('tar.gz', 'tar.bz2', 'tar.xz', '.tbz2')):
        ArkFile = tarfile.TarFile
    else:
        raise ValueError(f'{file_or_url} has unsupported archive type.')

    with tempfile.TemporaryDirectory() as tmp:
        if file_or_url.startswith(('http', 'ftp')):
            file_or_url = download(file_or_url, tmp, hexdigest, hasher,
                                   **kwargs)
        elif hasher and hexdigest:
            verify(file_or_url, hexdigest, hasher, **kwargs)

        logger.debug(f"Extracting {file_or_url} to {path}")
        with ArkFile.open(file_or_url) as archive:
            member_list = archive.getmembers()
            archive.extractall(path)
            return member_list


# noinspection PyUnresolvedReferences
def verify(file: Union[str, os.PathLike],
           hexdigest: str,
           hasher: Callable,
           chunk_size=2 ** 25):
    """verifies a downloaded file using hashlib"""
    logger.debug(f"Using {hasher.name} to verify archive.")
    logger.debug(f"Expecting hex digest: {hexdigest}")
    with open(file, 'rb') as f:
        chunk = f.read(chunk_size)
        while chunk:
            hasher.update(chunk)
            chunk = f.read(chunk_size)
    if hasher.hexdigest() != hexdigest:
        raise tegrity.err.InTegrityError(
            f"Hash verification failed for {file}.  "
            f"expected: {hexdigest} but got {hasher.hexdigest()}"
        )
