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

# import tegrity
# this file doesn't import tegrity up here, since it must live on it's own,

from typing import Iterable, Sequence, Mapping

__all__ = [
    '_fill_template',
    'init_first_boot_folder',
    'install_first_boot_scripts',
    'LOG_MODE',
    'run_scripts',
    'SCRIPT_FOLDER_NAME',
    'SCRIPT_MODE',
    'SCRIPT_NAME',
    'SERVICE_NAME',
    'SERVICE_TEMPLATE_FILE',
    'THIS_DIR',
    'THIS_SCRIPT_ABSPATH',
]

logger = logging.getLogger(__name__)
_utils_logger = logging.getLogger('utils')  # fakes utils module logging,
# otherwise they're logically in the wrong place in the log.

# most of these should probably not be overriden, but you can if you have good
# reason to.
SCRIPT_NAME = os.path.basename(__file__)
THIS_SCRIPT_ABSPATH = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_SCRIPT_ABSPATH)
SCRIPT_FOLDER_NAME = 'tegrity_fb'
SCRIPT_ABS_TARGET_PATH = os.path.join('/etc', SCRIPT_FOLDER_NAME, SCRIPT_NAME)
SERVICE_NAME = 'tegrity-fb.service'
SERVICE_TEMPLATE_FILE = 'tegrity-firstboot.service.in'
SERVICE_TEMPLATE_DEFAULTS = {
    'after': 'nvfb.service',
    'before': 'display-manager.service',
    'execstart': f"/usr/bin/python3 {SCRIPT_ABS_TARGET_PATH}"
}

# the permissions of the SCRIPT_FOLDER_NAME and executable contents
# set this tp 0o700 if you want the folder and scripts to be read only to all
# but the owner
SCRIPT_MODE = 0o755
# the absolute target path on the real filesystem:
# sometimes logs leave sensitive information in full view. It's best to leave
# this as the default just in case your first boot scripts are spitting out
# something sensitive.
LOG_MODE = 0o600


def _fill_template(
        template: str = SERVICE_TEMPLATE_FILE,
        parameters: Mapping[str, str] = None,) -> str:
    """
    :returns: a formatted first boot .service unit for systemd. Provides some
    more friendly errors for KeyError
    :param template: the template to fill out as string OR filename. If
    |template| contains brackets, |template| itself is formatted. Otherwise
    it's assumed to be a filename and an attempt is made to load and format it.
    :param parameters: the parameters to user to .format() the template

    >>> _fill_template(template='{foo}', parameters={'foo':'bar'})
    "bar"
    """
    if not parameters:
        parameters = SERVICE_TEMPLATE_DEFAULTS
    logger.debug(f"filling out template with parameters: {parameters}")
    if not all(c in template for c in ('{', '}')):
        with open(os.path.join(THIS_DIR, SERVICE_TEMPLATE_FILE)) as f:
            template = f.read()
    try:
        return template.format(**parameters)
    except KeyError as err:
        raise KeyError(
            f"Malformed template file or parameters. "
            f"Maybe extra or missing {{braces}}? Please see the example, ask for "
            f"help on Nvidia's devtalk forum, or modify the "
            f"_fill_template function in {SCRIPT_NAME} yourself."
        ) from err


def _install_service(rootfs, service_name=SERVICE_NAME):
    """installs a systemd service to a rootfs"""
    logger.debug("Installing service on rootfs.")
    unit_file = os.path.join(rootfs, 'lib', 'systemd', 'service', service_name)
    with open(unit_file, 'w') as f:
        f.write(_fill_template())
    command = ('systemctl', f'--root={rootfs}', 'enable', service_name)
    _run_one(command).check_returncode()


def _yes_or_no(input_text) -> bool:
    """prompts for a yes or no choices for |input_text|"""
    choice = ""
    while not choice.startswith(('y', 'n')):
        choice = input(f"{input_text} (y/n)").lower()
    return True if choice.startswith('y') else False


def _chmod(path, mode):
    """wraps os.chmod() and logs to debug level"""
    _utils_logger.debug(f"setting {path} to mode {str(oct(mode)[2:])}")
    return os.chmod(path, mode)


def _mkdir(path, mode):
    """wraps os.mkdir() and logs to debug level"""
    _utils_logger.debug(f"creating {path} with mode {str(oct(mode)[2:])}")
    return os.mkdir(path, mode)


def _copy(src, dest, **kwargs):
    """wraps shutil.copy() and logs to debug level"""
    _utils_logger.debug(f"copying {src} to {dest}")
    return shutil.copy(src, dest, **kwargs)


def _remove(path):
    """wraps os.remove() (or os.rmdir) and logs to debug level
    also deletes empty directories"""
    _utils_logger.debug(f"removing {path}")
    try:
        os.remove(path)
    except IsADirectoryError:
        try:
            os.rmdir(path)
        except FileNotFoundError as err:
            _utils_logger.error(f"{path} not found", err)
        except OSError as err:
            _utils_logger.error(f"{path} not empty", err)


def _run_one(*args, **kwargs) -> subprocess.CompletedProcess:
    """wraps subprocess.run but also logs the command"""
    if not args or not issubclass(type(args[0]), Sequence):
        raise ValueError(
            "Arguments must not be empty and first element must be a Sequence")
    _utils_logger.debug(f"running: {' '.join(args[0])}")
    return subprocess.run(*args, **kwargs)


def init_first_boot_folder(rootfs, overwrite=False, interactive=False):
    """
    initialises files and folders required by the script

    :param rootfs: the rootfs path
    :param overwrite: whether to clear out the target paths without asking
    :param interactive: if overwrite, prompt first
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
            if interactive and _yes_or_no(
                    f"are you sure you want to rm -rf {tegrity_fb}?"):
                shutil.rmtree(tegrity_fb)
            return init_first_boot_folder(rootfs)
    _chmod(tegrity_fb, SCRIPT_MODE)
    dest = os.path.join(tegrity_fb, os.path.basename(__file__))
    _copy(THIS_SCRIPT_ABSPATH, dest)
    _chmod(dest, SCRIPT_MODE)
    return tegrity_fb


def install_first_boot_scripts(rootfs, scripts: Iterable[os.PathLike],
                               overwrite=False,
                               interactive=False):
    """
    Installs first boot scripts to the rootfs (to be run once and then self
    destruct)

    :arg rootfs: full path to rootfs
    :arg scripts: an iterable (eg, tuple, list, generator) of scripts to be
    installed. They will be run in the order inserted into this function.
    :param overwrite: passed to init_first_boot_folder
    :param interactive: prompt before deleting on init_first_boot_folder
    """
    tegrity_fb = init_first_boot_folder(rootfs, overwrite, interactive=interactive)
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


def run_scripts(folder=None, cleanup=False):
    failed = []  # counter for failed script executions
    if not folder:
        folder = THIS_DIR
    for root, dirs, scripts in os.walk(folder):
        for script in sorted(scripts):
            if script == SCRIPT_NAME:
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


def main(rootfs: str = None,
         scripts: Iterable = None,
         overwrite: bool = False,
         run: str = None,
         cleanup: bool = False,
         interactive: bool = False) -> None:
    """
    if |rootfs| and |scripts|, installs the |scripts|, elif run whatever |run|
    points to and deletes the scripts that execute successfully with |cleanup|

    :param rootfs: the rootfs location
    :param scripts: the scripts
    :param overwrite: whether to overwrite existing scripts
    :param run: str of folder to run scripts in **if not rootfs and scripts**
    :param cleanup: deletes scripts that execute successfully.
    :param interactive: if |interactive| ask for confirmation before |cleanup|
    """
    if rootfs and scripts:
        install_first_boot_scripts(rootfs, scripts,
                                   overwrite=overwrite,
                                   interactive=interactive,)
    elif run:
        run_scripts(run, cleanup)


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description="to install and run first boot scripts on a rootfs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,)

    ap.add_argument(
        'rootfs', help=f"location of rootfs")
    ap.add_argument(
        'scripts', help="list of scripts to install to rootfs to execute in the "
        "order supplied here on first boot, **including duplicates**",
        nargs='+')
    ap.add_argument(

    )

    try:
        import tegrity
        # add --log-file and --verbose, specify that we're running interactively
        main(**tegrity.cli.cli_common(ap))
    except ImportError:
        # we're running standalone, just to run the scripts:
        tegrity = None
        ap = argparse.ArgumentParser("firstboot.py standalone mode")
        ap.add_argument(
            '--run', help="run scripts in this folder", default=THIS_DIR)
        ap.add_argument(
            '--cleanup', help="delete scripts after *successful* execution",
            action='store_true')
        main(**vars(ap.parse_args()))


if __name__ == '__main__':
    cli_main()
