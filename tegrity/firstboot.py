#!/usr/bin/python3 -sS

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

import itertools
import logging
import os
import shutil
import subprocess


from typing import Iterable, Sequence

__all__ = [
    'init_first_boot_folder',
    'install_first_boot_scripts',
    'run_scripts',
]
logger = logging.getLogger(__name__)

THIS_SCRIPT = os.path.basename(
    os.path.abspath(__file__))
THIS_SCRIPT_ABSPATH = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_SCRIPT_ABSPATH)

MAX_FIRST_BOOT_SCRIPTS = 999
SCRIPT_FOLDER_NAME = 'tegrity_fb'

SCRIPT_MODE = 0o755
# sometimes logs leave sensitive information in full view. It's best to leave
# this as the default just in case your first boot scripts are spitting out
# something sensitive.
LOG_MODE = 0o600

SERVICE_TEMPLATE = """# Tegrity First Boot Service
[Unit]
Description="Tegrity First Boot Service"
DefaultDependencies=no
Conflicts=shutdown.target
After={after}
Before={before}
ConditionPathIsReadWrite=/etc
ConditionFirstBoot=yes

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={execstart}
"""


def create_service_template(after: str, before: str, execstart: str):
    return SERVICE_TEMPLATE.format(
        after=after,
        before=before,
        execstart=execstart,
    )


def _yes_or_no(input_text) -> bool:
    """prompts for a yes or no choices for |input_text|"""
    choice = ""
    while not choice.startswith(('y', 'n')):
        choice = input(f"{input_text} (y/n)").lower()
    return True if choice.startswith('y') else False


def _chmod(path, mode):
    """wraps os.chmod() and logs to debug level"""
    logger.debug(f"setting {path} to mode {str(oct(mode)[2:])}")
    return os.chmod(path, mode)


def _mkdir(path, mode):
    """wraps os.mkdir() and logs to debug level"""
    logger.debug(f"creating {path} with mode {str(oct(mode)[2:])}")
    return os.mkdir(path, mode)


def _copy(src, dest, **kwargs):
    """wraps shutil.copy() and logs to debug level"""
    logger.debug(f"copying {src} to {dest}")
    return shutil.copy(src, dest, **kwargs)


def _remove(path):
    """wraps os.remove() (or os.rmdir) and logs to debug level
    also deletes empty directories"""
    logger.debug(f"removing {path}")
    try:
        os.remove(path)
    except IsADirectoryError:
        try:
            os.rmdir(path)
        except FileNotFoundError as err:
            logger.error(f"{path} not found", err)
        except OSError as err:
            logger.error(f"{path} not empty", err)


def init_first_boot_folder(rootfs, overwrite=False):
    """
    initialises files and folders required by the script

    :param rootfs: the rootfs path
    :param overwrite: whether to clear out the target paths without asking
    :returns: a path to the script folder
    """
    tegrity_fb = os.path.join(rootfs, 'etc', SCRIPT_FOLDER_NAME)
    logger.info(f"checking for first boot scripts under {tegrity_fb}")
    if not os.path.isdir(tegrity_fb):
        logger.debug(f"existing first boot script not found at {tegrity_fb}")
        try:
            _mkdir(tegrity_fb, SCRIPT_MODE)
        except FileNotFoundError as err:
            raise FileNotFoundError(
                "please check your --rootfs argument so it is pointing to a "
                "valid file system."
            ) from err
    else:
        logger.debug(f"found first boot script folder at {tegrity_fb}")
        if len(os.listdir(tegrity_fb)) and \
                (overwrite or _yes_or_no("First boot scripts exist. Erase? ")):
            logger.debug(f"deleting {tegrity_fb}")
            shutil.rmtree(tegrity_fb)
            return init_first_boot_folder(rootfs)
    _chmod(tegrity_fb, SCRIPT_MODE)
    dest = os.path.join(tegrity_fb, os.path.basename(__file__))
    _copy(THIS_SCRIPT_ABSPATH, dest)
    _chmod(dest, SCRIPT_MODE)
    return tegrity_fb


def install_first_boot_scripts(rootfs, scripts: Iterable[str], overwrite=False):
    """
    Installs first boot scripts to the rootfs (to be run once and then self
    destruct)

    :arg rootfs: full path to rootfs
    :arg scripts: an iterable (eg, tuple, list, generator) of scripts to be
    installed. They will be run in the order inserted into this function.
    :param overwrite: passed to init_first_boot_folder
    """
    tegrity_fb = init_first_boot_folder(rootfs, overwrite)
    logger.info(f"Installing first boot scripts to {tegrity_fb}")
    for index, filename in enumerate(scripts):
        if index == 100:
            raise RuntimeError(
                f"Maximum first boot scripts is 100 for sanity."
                f"If you need more than this, something is possibly wrong, but "
                f"more can be added manually")
        dest = os.path.join(
            # numbered filename, counting by 10:
            tegrity_fb,
            f"{str(index * 10).rjust(3, '0')}.{os.path.basename(filename)}"
        )
        _copy(filename, dest)
        _chmod(dest, SCRIPT_MODE)
    pass


def _run_one(*args, **kwargs) -> subprocess.CompletedProcess:
    """wraps subprocess.run but also logs the command"""
    if not args or not issubclass(type(args[0]), Sequence):
        raise ValueError(
            "Arguments must not be empty and first element must be a Sequence")
    logger.debug(f"running: {' '.join(args[0])}")
    return subprocess.run(*args, **kwargs)


def run_scripts(folder=None, cleanup=False):
    failed = []  # counter for failed script executions
    if not folder:
        folder = THIS_DIR
    for root, dirs, scripts in os.walk(folder):
        for script in sorted(scripts):
            if script == THIS_SCRIPT:
                # if the script is this file, ignore it, otherwise this script
                # will execute itself recursively forever
                continue
            if os.access(script, os.X_OK):
                args = (os.path.join(root, script),)
                logger.info(f"running: {' '.join(args)}")
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                log = os.path.join(root, f"{script}.log")
                log_fd = os.open(
                    log, os.O_CREAT | os.O_WRONLY | os.O_APPEND, LOG_MODE)
                with open(log_fd, 'a') as log:
# we're muxing the streams here
# https://docs.python.org/3/library/itertools.html#itertools.zip_longest
                    for stdout, stderr in itertools.zip_longest(
                            process.stdout, process.stderr):
                        stdout = stdout.decode()
                        log.write(stdout)
                        logger.debug(stdout)
                        if stderr:
                            stderr = stderr.decode()
                            log.write(stderr)
                            logger.error(
                                f"{os.path.basename(script)}:{stderr.rstrip()}")
                process.wait(timeout=10)
                if cleanup and not process.returncode:
                    _remove(script)
                if process.returncode:
                    failed.append(script)
                    logger.error(f"{script} failed")
            elif not script.endswith('.log'):
                logger.warning(
                    f"'{script}' was found in {root} but not marked executable")
    readme_msg = "Here you will find tegrity first boot logs.\n"
    if failed:
        logger.error(
            f"Some scripts failed to execute properly: "
            f"{[os.path.basename(s) for s in failed]} "
            f"You may attempt to re-run them manually from inside {folder}")
        readme_msg += "The below scripts in this folder failed first boot init" \
            "but may be re-run manually:\n{lines}\n".format(
                lines='\n'.join(failed))
    with open(os.path.join(folder, "README"), 'w') as readme:
        readme.write(readme_msg)
    if cleanup:
        # I may make this the default
        _remove(THIS_SCRIPT_ABSPATH)
    if not failed and cleanup:
        _remove(folder)


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description="First boot script helper script with no arguments will run"
                    "all executable scripts in the running folder *recursively*"
                    "and in alphanumeric order",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    ap.add_argument(
        '--rootfs', help=f"location of rootfs. with no other arguments, "
        f"initializes rootfs/etc/{SCRIPT_FOLDER_NAME} and systemd first boot"
        f"service file.")
    ap.add_argument(
        '--overwrite', help=f"*recursively* deletes "
        f"rootfs/etc/{SCRIPT_FOLDER_NAME} without asking for confirmation. "
        f"(requires --rootfs or --install)",
        action='store_true')
    ap.add_argument(
        '--install', help="list of scripts to install to rootfs (requires "
        "--rootfs). **will execute in the order supplied, including duplicates**",
        nargs='+')
    ap.add_argument(
        '--run', help="run scripts in the script's containing folder "
        "(this is the default behavior if no other arguments supplied)",
        default=THIS_DIR)
    ap.add_argument(
        '--cleanup', help="delete scripts and associated files after "
        "*successful* execution", action='store_true'
    )
    ap.add_argument(
        '-v', '--verbose', help="prints DEBUG log level to stdout",
        action="store_true")

    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.overwrite:
        if not args.rootfs and not args.install:
            raise RuntimeError("--overwrite requires --rootfs or --install")
    if args.install:
        if not args.rootfs:
            raise RuntimeError("--rootfs is required when using --install")
        install_first_boot_scripts(
            args.rootfs, args.install, args.overwrite)
    elif args.rootfs:
        init_first_boot_folder(args.rootfs, args.overwrite)
    elif args.run:
        run_scripts(args.run, args.cleanup)


if __name__ == '__main__':
    cli_main()
