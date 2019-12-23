import json
import logging
import os

import tegrity

from typing import (
    TYPE_CHECKING,
    Dict,
    MutableMapping,
)

import tegrity.settings

if TYPE_CHECKING:
    from argparse import ArgumentParser
else:
    ArgumentParser = None

logger = logging.getLogger(__name__)


def configure_logging(kwargs: MutableMapping) -> MutableMapping:
    # configure logging
    fh = logging.FileHandler(kwargs['log_file'])
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s::%(levelname)s::%(name)s::%(message)s'))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter())
    ch.setLevel(logging.DEBUG if kwargs['verbose'] else logging.INFO)
    # noinspection PyArgumentList
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=(fh, ch),
    )
    del kwargs['verbose'], kwargs['log_file']
    return kwargs


# def configure_config(kwargs: MutableMapping) -> MutableMapping:
#     # todo: save and load config to a file


def cli_common(ap: ArgumentParser,
               log: bool = True,
               # config: bool = True,
               ensure_sudo = True,) -> Dict:
    """
    Appends common command line options to an argument parser and returns
    kwargs ready to unpack into a main function. values that are None are
    stripped

    :arg ap: the argparse.ArgumentParser to append options to

    :param log: appends --log-file and --verbose
    :param ensure_sudo: raises PermissionError if user is not sudo
    """
    if log:
        ap.add_argument(
            '-l', '--log-file', help="where to store log file",
            default=os.path.join(
                tegrity.settings.DEFAULT_CONFIG_PATH, "tegrity.log",))
        ap.add_argument(
            '-v', '--verbose', help="prints DEBUG log level (logged anyway in "
            "--log-file)",
            action='store_true',)
    # if config:
    #     # add these two, for sanity, since there are a ton of options
    #     ap.add_argument(
    #         '--load-config', help="a config file to load (to run this script).")
    #     ap.add_argument(
    #         '--save-config', help="save a config to this file")

    # parse the arguments, getting the result back in dict format
    kwargs = vars(ap.parse_args())

    # todo: remove root requirement for image build
    if ensure_sudo:
        tegrity.utils.ensure_sudo()

    if log:
        kwargs = configure_logging(kwargs)

    # strip out the None values, so as to leave defaults in main() untouched.
    return {k: v for k, v in kwargs.items() if v is not None}
