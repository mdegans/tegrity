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

# This is a script to generate the SD card flashable image for
# jetson-nano platform

set -e

function usage()
{
	if [ -n "${1}" ]; then
		echo "${1}"
	fi

	echo "Usage:"
	echo "${script_name} -o <sd_blob_name> -s <sd_blob_size> -b <board> -r <revision>"
	echo "	sd_blob_name	- valid file name"
	echo "	sd_blob_size	- can be specified with G/M/K/B"
	echo "			- size with no unit will be B"
	echo "	board		- board name"
	echo "	revision	- SKU revision number"
	echo "Example:"
	echo "${script_name} -o sd-blob.img -s 4G -b jetson-nano -r 100"
	echo "${script_name} -o sd-blob.img -s 4096M -b jetson-nano -r 200"
	exit 1
}

function cleanup() {
	set +e
	if [ -n "${tmpdir}" ]; then
		umount "${tmpdir}"
		rmdir "${tmpdir}"
	fi

	if [ -n "${loop_dev}" ]; then
		losetup -d "${loop_dev}"
	fi
}
trap cleanup EXIT

function check_pre_req()
{
	this_user="$(whoami)"
	if [ "${this_user}" == "root" ]; then
		echo "ERROR: This script may not be run as root" > /dev/stderr
		usage
		exit 1
	fi

	while [ -n "${1}" ]; do
		case "${1}" in
		-h | --help)
			usage
			;;
		-b | --board)
			[ -n "${2}" ] || usage "Not enough parameters"
			board="${2}"
			shift 2
			;;
		-o | --outname)
			[ -n "${2}" ] || usage "Not enough parameters"
			sd_blob_name="${2}"
			shift 2
			;;
		-r | --revision)
			[ -n "${2}" ] || usage "Not enough parameters"
			rev="${2}"
			shift 2
			;;
		-s | --size)
			[ -n "${2}" ] || usage "Not enough parameters"
			sd_blob_size="${2}"
			shift 2
			;;
		*)
			usage "Unknown option: ${1}"
			;;
		esac
	done

	case "${rev}" in
	"100" | "200" | "300")
		;;
	*)
		usage "Incorrect Revision - Supported revisions - 100, 200, 300"
		;;
	esac

	if [ "${board}" == "" ]; then
		echo "ERROR: Invalid board name" > /dev/stderr
		usage
	else
		case "${board}" in
		jetson-nano)
			boardid="3448"
			target="p3448-0000-sd"
			storage="sdcard"
			;;
		*)
			usage "Unknown board: ${board}"
			;;
		esac
	fi

	if [ "${sd_blob_name}" == "" ]; then
		echo "ERROR: Invalid SD blob image name" > /dev/stderr
		usage
	fi

	if [ "${sd_blob_size}" == "" ]; then
		echo "ERROR: Invalid SD blob size" > /dev/stderr
		usage
	fi

	if [ ! -f "${l4t_dir}/flash.sh" ]; then
		echo "ERROR: ${l4t_dir}/flash.sh is not found" > /dev/stderr
		usage
	fi

	if [ ! -f "${l4t_tools_dir}/nvptparser.py" ]; then
		echo "ERROR: ${l4t_tools_dir}/nvptparser.py is not found" > /dev/stderr
		usage
	fi

	if [ ! -d "${bootloader_dir}" ]; then
		echo "ERROR: ${bootloader_dir} directory not found" > /dev/stderr
		usage
	fi

	if [ ! -d "${rfs_dir}" ]; then
		echo "ERROR: ${rfs_dir} directory not found" > /dev/stderr
		usage
	fi
}

function create_raw_image()
{
	echo "${script_name} - creating ${sd_blob_name} of ${sd_blob_size}..."
	dd if=/dev/zero of="${sd_blob_name}" bs=1 count=0 seek="${sd_blob_size}"
}

function create_signed_images()
{
	echo "${script_name} - creating signed images"

	pushd "${l4t_dir}"
	# Generate flashcmd.txt for signing images
	BOARDID="${boardid}" FAB="${rev}" "${l4t_dir}/flash.sh" "--no-flash" "--no-systemimg" "${target}" "mmcblk0p1"
	popd

	if [ ! -f "${bootloader_dir}/flashcmd.txt" ]; then
		echo "ERROR: ${bootloader_dir}/flashcmd.txt not found" > /dev/stderr
		exit 1
	fi

	# Generate signed images
	sed -i 's/flash; reboot/sign/g' "${l4t_dir}/bootloader/flashcmd.txt"
	pushd "${bootloader_dir}" > /dev/null 2>&1
	bash ./flashcmd.txt
	popd > /dev/null

	if [ ! -d "${signed_image_dir}" ]; then
		echo "ERROR: ${bootloader_dir}/signed directory not found" > /dev/stderr
		exit 1
	fi
}

function create_partitions()
{
	echo "${script_name} - create partitions"

	if [ ! -f "${signed_image_dir}/flash.xml" ]; then
		echo "ERROR: ${signed_image_dir}/flash.xml not found" > /dev/stderr
		exit 1
	fi

	partitions=($("${l4t_tools_dir}/nvptparser.py" "${signed_image_dir}/flash.xml" "${storage}"))
	part_type=8300 # Linux Filesystem

	sgdisk -og "${sd_blob_name}"
	for part in "${partitions[@]}"; do
		eval "${part}"
		part_size=$((${part_size} / 512)) # convert to sectors
		sgdisk -n "${part_num}":0:+"${part_size}" \
			-c "${part_num}":"${part_name}" \
			-t "${part_num}":"${part_type}" "${sd_blob_name}"
	done
}

function write_partitions()
{
	echo "${script_name} - write partitions"
	loop_dev="$(losetup --show -f -P "${sd_blob_name}")"
	tmpdir="$(mktemp -d)"

	for part in "${partitions[@]}"; do
		eval "${part}"
		target_file=""
		if [ "${part_name}" = "APP" ]; then
			echo "${script_name} - writing rootfs image"
			mkfs.ext4 -j "${loop_dev}p${part_num}"
			mount "${loop_dev}p${part_num}" "${tmpdir}"
			cp -a "${rfs_dir}"/* "${tmpdir}"
			umount "${tmpdir}"
		elif [ -e "${signed_image_dir}/${part_file}" ]; then
			target_file="${signed_image_dir}/${part_file}"
		elif [ -e "${bootloader_dir}/${part_file}" ]; then
			target_file="${bootloader_dir}/${part_file}"
		fi

		if [ "${target_file}" != "" ] && [ "${part_file}" != "" ]; then
			echo "${script_name} - writing ${target_file}"
			sudo dd if="${target_file}" of="${loop_dev}p${part_num}"
		fi
	done

	rmdir "${tmpdir}"
	losetup -d "${loop_dev}"
	tmpdir=""
	loop_dev=""
}

sd_blob_name=""
sd_blob_size=""
script_name="$(basename "${0}")"
l4t_tools_dir="$(cd "$(dirname "${0}")" && pwd)"
l4t_dir="${l4t_tools_dir%/*}"
if [ -z "${ROOTFS_DIR}" ]; then
	rfs_dir="${l4t_dir}/rootfs"
else
	rfs_dir="${ROOTFS_DIR}"
fi
bootloader_dir="${l4t_dir}/bootloader"
signed_image_dir="${bootloader_dir}/signed"
loop_dev=""
tmpdir=""

echo "********************************************"
echo "     Jetson-Nano SD Image Creation Tool     "
echo "********************************************"

check_pre_req "${@}"
create_raw_image
create_signed_images
create_partitions
write_partitions

echo "********************************************"
echo "   Jetson-Nano SD Image Creation Complete   "
echo "********************************************"
