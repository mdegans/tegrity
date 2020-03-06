#!/bin/bash

# Copyright (c) 2019, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#
# This host-side script applies the Debian packages to the rootfs dir
# pointed to by L4T_ROOTFS_DIR/opt/nvidia/l4t-packages.
#

readonly THIS_USER="$(whoami)"
readonly SCRIPT_NAME="$(basename $0)"
readonly THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

readonly L4T_NV_TEGRA_DIR="${THIS_DIR}"
# assumption: this script is part of the BSP and under L4T_DIR/nv_tegra
readonly L4T_DIR="$(dirname "${L4T_NV_TEGRA_DIR}")"
readonly L4T_KERN_DIR="${L4T_DIR}/kernel"
readonly L4T_BOOTLOADER_DIR="${L4T_DIR}/bootloader"

# the .deb destination on the rootfs:
readonly L4T_TARGET_DEB_DIR="/opt/nvidia/l4t-packages"
# this gets fed to proot's -q option and may include qemu options
readonly QEMU_BIN="qemu-aarch64-static"

# set this to "true" to print DEBUG by default
DEBUG="false"

set -e

# show the usages text
function ShowUsage() {
	local ScriptName=$1

	echo "Use: sudo "${ScriptName}" [--root|-r] [--help|-h]"
cat <<EOF
	This target-side script copies over tegra debian packages
	Options are:
	--root|-r
				   Specify root directory
	--help|-h
				   show this help
EOF
}

function ShowDebug() {
	echo "${SCRIPT_NAME} debug info:"
	echo "L4T_BOOTLOADER_DIR=${L4T_BOOTLOADER_DIR}"
	echo "L4T_DIR=${L4T_DIR}"
	echo "L4T_KERN_DIR=${L4T_KERN_DIR}"
	echo "L4T_NV_TEGRA_DIR=${L4T_NV_TEGRA_DIR}"
	echo "L4T_ROOTFS_DEB_DIR=${L4T_ROOTFS_DEB_DIR}"
	echo "L4T_ROOTFS_DIR=${L4T_ROOTFS_DIR}"
	echo "QEMU_BIN=${QEMU_BIN}"
	echo "THIS_DIR=${THIS_DIR}"
	echo "THIS_USER=${THIS_USER}"
	set -ex
}

# pre_deb_list includes Debian packages which must be installed before deb_list
pre_deb_list=()
deb_list=()
function AddDebsList() {
	local category="${1}"

	if [ -z "${category}" ]; then
		echo "Category not specified"
		exit 1
	fi

	for deb in "${L4T_ROOTFS_DEB_DIR}/${category}"/*.deb; do
		deb_name=$(basename ${deb})
		if [[ "${deb_name}" == "nvidia-l4t-ccp"* ]]; then
			pre_deb_list+=("${L4T_TARGET_DEB_DIR}/${category}/${deb_name}")
		else
			deb_list+=("${L4T_TARGET_DEB_DIR}/${category}/${deb_name}")
		fi
	done
}

function FailIfRoot() {
	if [ "${THIS_USER}" == "root" ]; then
		echo "This script should not be run as root"
		exit 1
	fi
}

# parse the command line first
TGETOPT=$(getopt -n "${SCRIPT_NAME}" --longoptions help,root: -o hcr: -- "$@")

eval set -- "${TGETOPT}"

while [ $# -gt 0 ]; do
	case "$1" in
	-h|--help) ShowUsage "$SCRIPT_NAME"; exit 1 ;;
	-r|--root) L4T_ROOTFS_DIR="$2" ;;
	-d|--debug) DEBUG="true" ;;
	--) shift; break ;;
	-*) echo "Terminating... wrong switch: $@" >&2 ; ShowUsage "$SCRIPT_NAME"; \
	exit 1 ;;
	esac
	shift
done

if [ $# -gt 0 ]; then
	ShowUsage "$SCRIPT_NAME"
	exit 1
fi

# check if the dir holding Debian packages exists in the BSP
if [ ! -d "${L4T_NV_TEGRA_DIR}/l4t_deb_packages" ]; then
	echo "No debian packages found. Bad BSP tarball?"
	exit 1
fi

# use default rootfs dir if none is set
if [ -z "$L4T_ROOTFS_DIR" ]; then
	L4T_ROOTFS_DIR="${L4T_DIR}/rootfs"
fi

echo "Root file system directory is ${L4T_ROOTFS_DIR}"

# dir on target rootfs to keep Debian packages prior to installation
L4T_ROOTFS_DEB_DIR="${L4T_ROOTFS_DIR}${L4T_TARGET_DEB_DIR}"

if [ "${DEBUG}" == "true" ]; then
	ShowDebug
fi

# fail if the current user is root
FailIfRoot

# copy debian packages and installation script to rootfs
echo "Copying public debian packages to rootfs"
install -m 755 -d "${L4T_ROOTFS_DEB_DIR}/userspace"
install -m 755 -d "${L4T_ROOTFS_DEB_DIR}/kernel"
install -m 755 -d "${L4T_ROOTFS_DEB_DIR}/bootloader"
install -m 755 -d "${L4T_ROOTFS_DEB_DIR}/standalone"

# todo: fix or defer python-jetson-gpio installation
#  which fails with exec format error if uncommented:
#cp "${L4T_DIR}/tools"/*.deb "${L4T_ROOTFS_DEB_DIR}/standalone"
#AddDebsList "standalone"
cp "${L4T_NV_TEGRA_DIR}/l4t_deb_packages"/*.deb \
"${L4T_ROOTFS_DEB_DIR}/userspace"
AddDebsList "userspace"
debs=(`find "${L4T_KERN_DIR}" -maxdepth 1 -iname "*.deb"`)
if [ "${#debs[@]}" -ne 0 ]; then
	cp "${L4T_KERN_DIR}"/*.deb "${L4T_ROOTFS_DEB_DIR}/kernel"
	AddDebsList "kernel"
else
	echo "Kernel debian package NOT found. Skipping."
fi
debs=(`find "${L4T_BOOTLOADER_DIR}" -maxdepth 1 -iname "*.deb"`)
if [ "${#debs[@]}" -ne 0 ]; then
	cp "${L4T_BOOTLOADER_DIR}"/*.deb "${L4T_ROOTFS_DEB_DIR}/bootloader"
	AddDebsList "bootloader"
else
	echo "Bootloader debian package NOT found. Skipping."
fi

if [ "${#deb_list[@]}" -eq 0 ]; then
	echo "No packages to install. There might be something wrong"
	exit 1
fi

if [ -e "${L4T_BOOTLOADER_DIR}/t186ref/cfg/nv_boot_control.conf" ]; then
	# copy nv_boot_control.conf to rootfs to support bootloader
	# and kernel updates
	echo "Copying nv_boot_control.conf to rootfs"
	cp "${L4T_BOOTLOADER_DIR}/t186ref/cfg/nv_boot_control.conf" \
	"${L4T_ROOTFS_DIR}/etc/"
fi

function ProotRun() {
	# -S can't be used because nvidia-l4t-init modifies /etc/hosts
	proot -0 -r "${L4T_ROOTFS_DIR}" -w / -q "${QEMU_BIN}" \
		-b /dev \
		-b /etc/host.conf \
		-b /proc \
		-b /sys \
		-b /tmp \
		"$@"
}

echo "Start L4T BSP package installation"
echo "Installing Jetson OTA server key in rootfs"
install -m 644 -T "${L4T_NV_TEGRA_DIR}/jetson-ota-public.key" \
	"${L4T_ROOTFS_DIR}/etc/apt/trusted.gpg.d/jetson-ota-public.asc"

pushd "${L4T_ROOTFS_DIR}"
touch "${L4T_ROOTFS_DEB_DIR}/.nv-l4t-disable-boot-fw-update-in-preinstall"
echo "Installing BSP Debian packages in ${L4T_ROOTFS_DIR}"
if [ "${#pre_deb_list[@]}" -ne 0 ]; then
	LC_ALL=C ProotRun dpkg -i --path-include="/usr/share/doc/*" "${pre_deb_list[@]}"
fi
LC_ALL=C ProotRun dpkg -i --path-include="/usr/share/doc/*" "${deb_list[@]}"
rm -f "${L4T_ROOTFS_DEB_DIR}/.nv-l4t-disable-boot-fw-update-in-preinstall"
popd

echo "Removing stashed Debian packages from rootfs"
rm -rf "${L4T_ROOTFS_DEB_DIR}"

echo "L4T BSP package installation completed!"
exit 0
