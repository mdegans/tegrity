#!/usr/bin/python3 -sSE
import os
import logging
import tegrity
from tegrity.__main__ import ensure_system_requirements

logger = logging.getLogger(__name__)

PIP3 = '/usr/bin/pip3'


def install(prefix=None):
    """installs tegrity using pip3 to /usr/local/"""
    logger.info(f"Installing {tegrity.__name__}")
    ensure_system_requirements()
    this_dir = os.path.dirname(__file__)
    command = [PIP3, 'install', '--upgrade', '--no-cache']
    if prefix:
        command.extend(['--prefix', prefix])
    command.append(this_dir)
    tegrity.utils.run(command).check_returncode()


def uninstall():
    """uninstalls tegrity"""
    logger.info(f"Uninstalling {tegrity.__name__}")
    tegrity.utils.run(
        (PIP3, 'uninstall', '--no-cache', tegrity.__name__)
    )


def cli_main():
    """"""
    import argparse
    ap = argparse.ArgumentParser(
        description="Installs or upgrades Tegrity",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument('-v', '--verbose', help="prints DEBUG log level",
                    action='store_true')
    ap.add_argument('-u', '--uninstall', help="uninstalls tegrity",
                    action='store_true')
    ap.add_argument('--prefix', help='override prefix (see pip manual)')
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.uninstall:
        uninstall()
        return
    install(args.prefix)


if __name__ == '__main__':
    cli_main()
