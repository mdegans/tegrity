#!/usr/exe/python3 -sS

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

import tegrity

__all__ = [
    'install'
]

logger = logging.getLogger(__name__)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_TEMPLATE = os.path.join(THIS_DIR, 'tegrity-service-simple.service.in')
DEFAULT_AFTER = 'basic.target'
DEFAULT_BEFORE = 'default.target'
DEFAULT_WANTED_BY = 'default.target'
DEFAULT_BINDIR = ('usr', 'local', 'exe')
DEFAULT_UNIT_PATH = ('lib', 'systemd', 'system')


def is_enabled(service_name, rootfs) -> bool:
    """returns True if a service is enabled on a rootfs, False otherwise"""
    retcode = tegrity.utils.run(
        ('systemctl', f'--root={rootfs}', 'is-enabled', service_name)
    ).returncode
    if retcode:
        return False
    return True


def is_active(service_name) -> bool:
    """returns True if a service is running on the host. False otherwise."""
    retcode = tegrity.utils.run(
        ('systemctl', 'is-active', service_name)
    ).returncode
    if retcode:
        return False
    return True


def start(service_name):
    """stops a systemd service on the host"""
    logger.debug(f"starting {service_name}")
    tegrity.utils.run(
        ('systemctl', 'start', service_name)
    ).check_returncode()


def stop(service_name):
    """stops a systemd service on the host"""
    logger.debug(f"stopping {service_name}")
    tegrity.utils.run(
        ('systemctl', 'stop', service_name)
    ).check_returncode()


def install(executable: str, rootfs: str,
            after: str = DEFAULT_AFTER,
            before: str = DEFAULT_BEFORE,
            wanted_by: str = DEFAULT_WANTED_BY):
    """Installs executables as simple systemd services on a rootfs"""
    # check all files and paths exist (yeah, this isn't pythonic, but whatever)
    if not os.path.isfile(executable):
        raise FileNotFoundError(f"{executable} not found.")
    bindir = os.path.join(rootfs, *DEFAULT_BINDIR)
    if not os.path.isdir(bindir):
        raise FileNotFoundError(f"{bindir} not found. Wrong rootfs path?")
    unitpath = os.path.join(rootfs, *DEFAULT_UNIT_PATH)
    if not os.path.isdir(unitpath):
        raise FileNotFoundError(
            f"{unitpath} not found. Does this rootfs use systemd?")

    # copy the file to the bindir and make it executable
    exec_dest = os.path.join(bindir, executable)
    tegrity.utils.copy(executable, exec_dest)
    tegrity.utils.chmod(exec_dest, 0o755)

    # configure executable paths and service paths
    exec_name = os.path.basename(executable)
    logger.debug(f"executable basename: {exec_name}")
    execstart = os.path.join('/', *DEFAULT_BINDIR, exec_name)
    logger.debug(f"absolute path on rootfs (execstart): {execstart}")
    service_basename = f"{os.path.splitext(exec_name)[0]}.service"
    service_filename = os.path.join(unitpath, service_basename)

    # fill in the template and write it out
    logger.debug(f"filling in template: {DEFAULT_TEMPLATE}")
    with open(DEFAULT_TEMPLATE) as template_file:
        unit = template_file.read().format(
            after=after,
            before=before,
            exec_name=exec_name,
            execstart=execstart,
            wanted_by=wanted_by,
        )
    logger.debug(f"writing filled out template to {service_filename}")
    with open(service_filename, 'w') as service_file:
        service_file.write(unit)

    if is_enabled(service_basename, rootfs):
        logger.info("service seems to already be enabled.")
    else:
        logger.info(f"enabling {service_basename} on rootfs")
        tegrity.utils.run(
            ('systemctl', f'--root={rootfs}', 'enable', service_basename)
        ).check_returncode()


def cli_main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Installs executables as simple systemd services on a rootfs",
        epilog="Useful list of common targets: https://www.freedesktop.org/software/systemd/man/systemd.special.html",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    ap.add_argument('executable',
                    help="the executable/script to install as a service")
    ap.add_argument('rootfs', help="the path to the rootfs to use")
    ap.add_argument(
        '--after', help="start the executable after this .target or .service",
        default=DEFAULT_AFTER,
    )
    ap.add_argument(
        '--before', help="start the executable before this .target or .service",
        default=DEFAULT_BEFORE
    )
    ap.add_argument(
        '--wanted-by', help="see systemd documentation",
        default=DEFAULT_WANTED_BY
    )
    # todo: implement (will require a bunch of qemu code)
    # ap.add_argument(
    #     '--user', help="run the script as a specific user on the rootfs, "
    #                    "adding the user if necessary (default is root)"
    # )
    ap.add_argument(
        '--verbose', help="print the DEBUG log level", action='store_true'
    )

    kwargs = vars(ap.parse_args())

    # configure logging
    logging.basicConfig(
        level=logging.DEBUG if kwargs['verbose'] else logging.INFO
    )
    del kwargs['verbose']
    try:
        install(**kwargs)
    except PermissionError as err:
        raise PermissionError(
            "depending on your rootfs permissions, you may need to run this "
            "script as root."
        ) from err


if __name__ == '__main__':
    cli_main()
