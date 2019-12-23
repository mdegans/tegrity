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
import pwd
import sqlite3

from typing import (
    List,
)

import tegrity

# todo: sanity checking from database input, try to break the system using
#  a bad sdkm.db file
logger = logging.getLogger(__name__)

__all__ = [
    'NANO_DEV_ID',
    'NANO_PROD_ID',
    'NANO_IDS',
    'TX1_ID',
    'TX2_ID',
    'XAVIER_ID',
    'SUPPORTED_IDS',
    'MODEL_NAME_MAP',
    'filename',
    'connect',
    'get_bundles',
    'get_l4t_path',
    'bundle_formatter'
]

# Production IDs
NANO_DEV_ID = "P3448-0000"
NANO_PROD_ID = "P3448-0020"
NANO_IDS = {NANO_DEV_ID, NANO_PROD_ID}
# todo: look tx up
TX1_ID = "todo: look me up"
TX2_ID = "todo: look me up"
XAVIER_ID = "P2888"

# Currently only Jetson Nano supported (Xavier next)
SUPPORTED_IDS = {NANO_DEV_ID}

MODEL_NAME_MAP = {
    XAVIER_ID: "Jetson Xavier",
    NANO_DEV_ID: "Jetson Nano Development Module",
    NANO_PROD_ID: "Jetson Nano Production Module",
    TX1_ID: "Jetson TX-1",
    TX2_ID: "Jetson TX-2",
}


def filename():
    """
    Gets the SDKM db filename

    :raises: FileNotFoundError if sdkm.db not found

    >>> import tegrity.db
    >>> fn = tegrity.db.filename()
    >>> fn.endswith('sdkm.db')
    True
    """
    username = tegrity.utils.real_username()
    homedir = pwd.getpwnam(username)[5]
    db_filename = os.path.join(homedir, '.nvsdkm', 'sdkm.db')
    if not os.path.isfile(db_filename):
        raise FileNotFoundError(
            f"{db_filename} not found. {tegrity.err.NO_SDKM}")
    logger.debug(f"Database found at {db_filename}")
    return db_filename


def connect() -> sqlite3.Connection:
    """
    :returns: sqlite3.Connection object to SDKM database with sqlite3.Row as the
    connection.row_factory

    >>> connect()
    <sqlite3.Connection object at ...>
    """
    db_file = filename()
    logger.debug(f"Connecting to {db_file}")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn


def get_bundles(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """
    :returns: a list of sqlite3.Row (dicts with the column name as key)

    :raises: RuntimeError if no bundles found

    >>> conn = connect()
    >>> bundles = get_bundles(conn)
    >>> type(bundles) is list
    True
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM bundles WHERE targetHW != 'host' AND status == 'success'")
    bundles = cur.fetchall()
    if not bundles:
        raise RuntimeError(
            f"No bundles found. {tegrity.err.BUNDLE_REINSTALL}")
    return [bundle for bundle in bundles if bundle['targetHW'] in SUPPORTED_IDS]


def get_l4t_path(bundle: sqlite3.Row):
    """Gets the Linux_for_Tegra path for a given bundle"""
    return tegrity.utils.join_and_check(
        bundle["targetImageDir"], "Linux_for_Tegra")


def bundle_formatter(bundle: sqlite3.Row) -> str:
    """:returns: a formatted str representing a bundle row (for choices)"""
    return ' '.join(
        (bundle['title'],
         f"(Rev. {bundle['revision']})",
         'for',
         MODEL_NAME_MAP[bundle['targetHW']]),
    )


def autodetect_hwid(l4t, conn: sqlite3.Connection = None):
    """autodetects a hardward id (TargetHW) from Linux_for_Tegra path"""
    l4t = os.path.abspath(l4t)
    if not os.path.isdir(l4t) or os.path.basename(l4t) != "Linux_for_Tegra":
        raise FileNotFoundError(
            f"{l4t} does not appear to be a Linux_for_Tegra folder")
    if not conn:
        with tegrity.db.connect() as conn:
            bundles = tegrity.db.get_bundles(conn)
    else:
        bundles = tegrity.db.get_bundles(conn)
    for bundle in bundles:
        if l4t == tegrity.db.get_l4t_path(bundle):
            hwid = bundle['targetHW']
            if hwid not in tegrity.db.MODEL_NAME_MAP:
                raise NotImplemented(f"{hwid} currently unsupported")
            logger.debug(
                f"detected {tegrity.db.MODEL_NAME_MAP[hwid]} for {l4t}")
            return hwid


if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
