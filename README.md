# Tegrity

Is intended to help you build system images for Nvidia Jetson with:

* customized kernels, using a menu
* rootfs customization support

Tegrity currently only supports Jetson Nano, but support is planned for other
boards, starting with Xavier.

## Requirements:

Tegrity requires that you have SDK manager installed and have downloaded the
bundle for your Tegra development platform. If you have run SDK manager to 
flash your platform, chances are you've done this. Tegrity will find your SDK
Manager installation paths automatically using `~/.nvsdk/sdkm.db` to determine
appropriate paths.

## Installation:
To install or upgrade, obtain the files using git directly or from a release 
zip.
```
(cd into tegrity folder)
sudo install.py
```
To uninstall, run `sudo install.py --uninstall`

Tegrity is available on pypi as a placeholder, however it's not recommended to 
rely on pypi since at the time of writing pypi does not enforce MFA to upload 
packages. Also, a simple misspelling might result in malware being installed.

## To build a system image:
Up to date usage can be found by running `tegrity --help.`
```
 $ tegrity --help
usage: tegrity [-h] [--localversion LOCALVERSION]
               [--save-kconfig SAVE_KCONFIG] [--load-kconfig LOAD_KCONFIG]
               [--menuconfig] [--rootfs-source ROOTFS_SOURCE] [-l LOG_FILE]
               [-v]

Helps bake Tegra OS images

optional arguments:
  -h, --help            show this help message and exit
  --localversion LOCALVERSION
                        override local version string (kernel name suffix).
                        (default: -tegrity)
  --save-kconfig SAVE_KCONFIG
                        save kernel config to this file (default: None)
  --load-kconfig LOAD_KCONFIG
                        load kernel config from this file (default: None)
  --menuconfig          customize kernel config interactively using a menu
                        (WARNING: here be dragons! While it's unlikely, you
                        could possibly damage your Tegra or connected devices
                        if the kernel is mis-configured). (default: False)
  --rootfs-source ROOTFS_SOURCE
                        Location of rootfs to download/extract/copy from. may
                        be a url, path to a tarball, or a local directory path
                        specify 'download' to download a new, bundle
                        appropriate, copy from Nvidia. No arguments will use
                        the existing rootfs. (default: None)
  -l LOG_FILE, --log-file LOG_FILE
                        where to store log file (default:
                        /home/your_user/.tegrity/tegrity.log)
  -v, --verbose         prints DEBUG log level (DEBUG is logged anyway in the
                        (default: False)
```

### Kernel options explanation

`--localversion` overrides the local version string to add to the kernel 
(version suffix when running `uname -r`)

`--save-kconfig` saves a kernel config to a target location after configure 
is finished so that you may load it later to build an identical or updated 
kernel with the same configuration.

`--load-kconfig` loads a saved kernel configuration. It can be used in 
conjunction with `--menuconfig` and/or `--save-kconfig` to further customize 
(and save) the kernel config. Without this option the default Tegra defconfig is
used.

`--menuconfig` runs menuconfig, a menu based configurator for the kernel. This 
can be used to customize the supplied or default kernel configuration. You can 
save and load configurations directly from this interface or by using the above 
options.

### Rootfs options explanation

`--rootfs-source` Source to copy a rootfs from (local tarball, tarball at https
url, or local folder). The destination is always under your selected bundle's 
Linux_for_Tegra path. A timestamped backup of any existing rootfs will be made
automatically. Without this option, the existing rootfs will be used.
if "download" is supplied to this option, the default rootfs tarball will be
downloaded. Please see rootfs.py for the URLs and SHAs used if you wish to
customize or update this default (if NVIDIA posts a new release, for example).

### Logging options explanation

`-l`, `--log-file` specifies the location to store the log file. All messages
are logged to this file, even the DEBUG level. Since this script runs as root 
and sensitive information is occasionally dumped to log files, the default
owner for the folder is root:root and the mode 0700. To read the log run 
`sudo less ~/.tegrity/tegrity.log`

`-v`, `--verbose` prints the DEBUG log level.

## Why the name?
It is *absolutely not* a South Park reference. It was chosen for other reasons
which are completely unfunny and not at all imaginary.
