#!/bin/bash

readonly BSP_NANO_TX1_URL="https://developer.nvidia.com/embedded/dlc/r32-3-1_Release_v1.0/t210ref_release_aarch64/Tegra210_Linux_R32.3.1_aarch64.tbz2"
readonly BSP_NANO_TX1_FILENAME="Tegra210_Linux_R32.3.1_aarch64.tbz2"
readonly BSP_TX2_XAVIER_URL="https://developer.nvidia.com/embedded/dlc/r32-3-1_Release_v1.0/t186ref_release_aarch64/Tegra186_Linux_R32.3.1_aarch64.tbz2"
readonly BSP_TX2_XAVIER_FILENAME="Tegra186_Linux_R32.3.1_aarch64.tbz2"

set -ex
umask 22

function show_usage() {
    echo "Usage: $(basename $0) [nano | tx1 | tx2 | xavier]"
}

function verify_downloads() {
    sha512sum -c --ignore-missing "/scripts/checksums.txt"
}

function main() {
    # parse arguments
    case "${1}" in
        "nano" | "tx1")
            BSP="${BSP_NANO_TX1_URL}"
            BSP_FILENAME="${BSP_NANO_TX1_FILENAME}"
            ;;
        "tx2" | "xavier")
            BSP="${BSP_TX2_XAVIER_URL}"
            BSP_FILENAME="${BSP_TX2_XAVIER_FILENAME}"
            ;;
        *)
            >&2 echo "board must be nano, tx1, tx2, or xavier"
            show_usage
            exit 1
            ;;
    esac
    cd /tmp
    wget -nv "${BSP}"
    verify_downloads
    cd /
    umask 22
    tar -I lbzip2 -xmf "/tmp/${BSP_FILENAME}" --no-same-permissions
    rm "/tmp/${BSP_FILENAME}"
}

main "${1}"
