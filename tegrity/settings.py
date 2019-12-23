import os
import shutil

# the CONFIG_PATH just points to the logs, cache, and saved configurations.

# change this to 755 if you want your ~/.tegrity folder to be world readable
import tegrity

CONFIG_PATH_MODE = 0o700
# change this if conflict with an existing ~/.tegrity folder you want to keep
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), f".tegrity")

# for download.py
# todo: implement, since python bzip is really slow
LBZIP2 = shutil.which('lbzip2')

# for kernel.py
DEFAULT_LOCALVERSION = '-tegrity'
NANO_TX1_KERNEL_URL = "https://developer.nvidia.com/embedded/dlc/r32-3-1_Release_v1.0/Sources/T210/public_sources.tbz2"
NANO_TX1_KERNEL_SHA512 = "f9729758ff44f9b18ec78a3e99634a8cac1ca165f40cda825bc18f6fdd0b088baac5a5c0868167a420993b3a7aed78bc9a43ecd7dc5bba2c75ca20c6635573a6"
XAVIER_TX2_KERNEL_URL = "https://developer.nvidia.com/embedded/dlc/r32-3-1_Release_v1.0/Sources/T186/public_sources.tbz2"
XAVIER_TX2_KERNEL_SHA512 = "78e6d3cc67dcbdf27cb21f4cbbabb7a5b89ca813f2aaeb60a06ed8f797e6ec46d06bb0e915bfc292302c721dbce9b27492dbf07ee4ae084ca748ecd65eaae994"
# the path to the kernel_src.tbz2 inside public_sources.tbz2
KERNEL_TARBALL_PATH = ('Linux_for_Tegra', 'source', 'public', 'kernel_src.tbz2',)
# the path to the kernel inside kernel_src.tbz2
KERNEL_PATH = ('kernel', 'kernel-4.9')

# for rootfs.py
# urls, shas, and supported model numbers for their rootfs
L4T_ROOTFS_URL = "https://developer.nvidia.com/embedded/r32-2-3_Release_v1.0/t210ref_release_aarch64/Tegra_Linux_Sample-Root-Filesystem_R32.2.3_aarch64.tbz2"
L4T_ROOTFS_SHA512 = "15075b90d2e6f981e40e7fdd5b02fc1e3bbf89876a6604e61b77771519bf3970308ee921bb39957158153ba8597a31b504f5d77c205c0a0c2d3b483aee9f0d4f"
UBUNTU_BASE_URL = "http://cdimage.ubuntu.com/ubuntu-base/releases/18.04.3/release/ubuntu-base-18.04-base-arm64.tar.gz"
UBUNTU_BASE_SHA_256 = "9193fd5f648e12c2102326ee6fdc69ac59c490fac3eb050758cee01927612021"
NV_SOURCES_LIST = ('etc', 'apt', 'sources.list.d', "nvidia-l4t-apt-source.list")
NV_SOURCES_LIST_TEMPLATE = """deb https://repo.download.nvidia.com/jetson/common r32 main
deb https://repo.download.nvidia.com/jetson/{soc} r32 main"""
# this is a mapping between board id and appropriate SOC to fill in the repo url
BOARD_ID_TO_SOC = {
    tegrity.db.NANO_DEV_ID: 't210'
}