# Tegrity

Is a collection of scripts intended to help you build system images for Nvidia 
Jetson with:

* customized kernels, using menuconfig
* rootfs customization support (install and remove packages)

Tegrity currently only supports Jetson Nano Development version, but support is 
planned for other boards, starting with Xavier.

## Requirements:

Tegrity requires that you have SDK manager installed and have downloaded the
bundle for your Tegra development platform. If you have run SDK manager to 
flash your platform, chances are you've done this.

## Installation:
To install or upgrade, obtain the files using git directly or from a release 
zip.
```
(cd into tegrity folder)
sudo ./install.py
```
To uninstall, run `sudo install.py --uninstall`

Tegrity is available on pypi as a placeholder, however it's not recommended to 
rely on pypi since at the time of writing pypi does not enforce MFA to upload 
packages. Also, a simple misspelling might result in malware being installed.

## To build a system image:

The main script is 'tegrity' and runs all the others with appropriate options.

```
 $ tegrity --help
usage: tegrity [-h] [--cross-prefix CROSS_PREFIX]
               [--firstboot FIRSTBOOT [FIRSTBOOT ...]]
               [--public-sources PUBLIC_SOURCES]
               [--public-sources-sha512 PUBLIC_SOURCES_SHA512]
               [--build-kernel] [--kernel-load-config KERNEL_LOAD_CONFIG]
               [--kernel-save-config KERNEL_SAVE_CONFIG]
               [--kernel-localversion KERNEL_LOCALVERSION]
               [--kernel-menuconfig] [--rootfs-source ROOTFS_SOURCE]
               [--rootfs-source-sha512 ROOTFS_SOURCE_SHA512] [-o OUT]
               [-l LOG_FILE] [-v]
               l4t_path

Helps bake Tegra OS images.

positional arguments:
  l4t_path              path to desired Linux_for_Tegra path.

optional arguments:
  -h, --help            show this help message and exit
  --cross-prefix CROSS_PREFIX
                        the default cross prefix (default:
                        /usr/local/bin/aarch64-linux-gnu-)
  --firstboot FIRSTBOOT [FIRSTBOOT ...]
                        list of first boot scripts to install (default: None)
  --public-sources PUBLIC_SOURCES
                        url or local path to a public sources tarball.
                        (default: https://developer.nvidia.com/embedded/dlc/r3
                        2-3-1_Release_v1.0/Sources/T210/public_sources.tbz2)
  --public-sources-sha512 PUBLIC_SOURCES_SHA512
                        public sources sha512 expected (default: f9729758ff44f
                        9b18ec78a3e99634a8cac1ca165f40cda825bc18f6fdd0b088baac
                        5a5c0868167a420993b3a7aed78bc9a43ecd7dc5bba2c75ca20c66
                        35573a6)
  --build-kernel        builds the kernel (default: False)
  --kernel-load-config KERNEL_LOAD_CONFIG
                        loads kernel configuration from this file (default:
                        None)
  --kernel-save-config KERNEL_SAVE_CONFIG
                        save kernel configuration to this file (default: None)
  --kernel-localversion KERNEL_LOCALVERSION
                        local version string for kernel (default: -tegrity)
  --kernel-menuconfig   interactively configure kernel (default: False)
  --rootfs-source ROOTFS_SOURCE
                        url or local path to rootfs tarball / directory,
                        specify "l4t" to download a new default rootfs, or
                        "ubuntu_base" to get an Ubuntu Base rootfs. (default:
                        None)
  --rootfs-source-sha512 ROOTFS_SOURCE_SHA512
                        sha512sum of rootfs tarball (default: None)
  -o OUT, --out OUT     the out path (for sd card image, etc) (default: None)
  -l LOG_FILE, --log-file LOG_FILE
                        where to store log file (default:
                        /home/mdegans/.tegrity/tegrity.log)
  -v, --verbose         prints DEBUG log level (logged anyway in --log-file)
                        (default: False)

```

To build your system step by step, for more control, you may choose instead to 
run individual scripts in order:

1. `tegrity-toolchain` - to install or update a toolchain
2. `tegrity-kernel` - to build a kernel
3. `tegrity-rootfs` - to download or setup a new rootfs
4. `tegrity-qemu` - to run scripts on a rootfs or enter it interactively
5. `tegrity-image` - to build the final image (currently only creates sd card for 
Jetson Nano Development)

each of these scripts have their own `--help` options

Tegrity also installs a system python package, `tegrity`, allowing you to create
your own scripts with the same building blocks, however it's not recommended
to do this currently since the API is in shift. *However* `tegrity.qemu.QemuRunner`
will probably not change much and some may find it very useful in it's current
state.

basic usage:

```python
import tegrity

rootfs = '/path/to/a/rootfs'
script = '/path/to/a/script.sh'

with tegrity.qemu.QemuRunner(rootfs) as runner:
    # the same exact interface as subprocess.run:
    runner.run_cmd(('apt', 'update'))
    # the userspec parameter can be used to set a user (passed to chroot)
    runner.run_cmd(('vi', '/home/marco/.bashrc'), userspec="marco:marco")
    # .run_script can be used to copy a script to a rootfs and run it
    # (with options), deleting it afterward (untested):
    runner.run_script(script, '-o', 'output.whatever')
```

Since QemuRunner is [a context manager](https://docs.python.org/3/reference/datamodel.html#context-managers),
it will automatically mount the necessary special filesystems, bind mount or 
copy qemu-aarch64-static as appropriate, and no matter what happens, unmount the
special filesystems in reverse order and clean up on leaving the context.

Additional options for QemuRunner construction are available (eg. additional 
mounts, overriding mounts, override qemu binary location, etc). It's recommended
for now to read the relavent portions of qemu.py