#!/bin/bash

readonly ROOTFS="https://developer.nvidia.com/embedded/dlc/r32-3-1_Release_v1.0/t186ref_release_aarch64/Tegra_Linux_Sample-Root-Filesystem_R32.3.1_aarch64.tbz2"
readonly ROOTFS_FILENAME="Tegra_Linux_Sample-Root-Filesystem_R32.3.1_aarch64.tbz2"

set -ex

function fail_if_root() {
    if [[ "$(whoami)" == "root" ]]; then
        >&2 echo "this script should not be run as root"
    fi
}

function verify_downloads() {
    sha512sum -c --ignore-missing /scripts/checksums.txt
}

function download_rootfs() {
    cd /tmp
    wget -nv "${ROOTFS}"
    verify_downloads
    cd /Linux_for_Tegra/rootfs
    tar -I lbzip2 -xpmf ../../tmp/"${ROOTFS_FILENAME}"
    rm /tmp/"${ROOTFS_FILENAME}"
}

download_rootfs