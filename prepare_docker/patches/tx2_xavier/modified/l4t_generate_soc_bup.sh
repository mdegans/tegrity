#!/bin/bash

# Copyright (c) 2018-2019, NVIDIA CORPORATION.  All rights reserved.
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

# This script generates bootloader and kernel multi-specification BUP
# update payloads for Jetson boards

set -e

function usage()
{
	if [ -n "${1}" ]; then
		echo "${1}"
		echo ""
	fi

	echo "This script generates bootloader and kernel payloads based on the"
	echo "specifications listed in the vars at the end this script and the"
	echo "supplied <target_soc>."
	echo ""
	echo "Usage:"
	echo "	${script_name} [-h|--help] [-u <key_file>] <target_soc>"
	echo "	-h|--help      Displays this help prompt."
	echo "	-u <key_file>  Optional RSA key file for signing binaries."
	echo "	<target_soc>   Must be either \"t18x\", \"t19x\" or \"t21x\"."
	echo "                 Must be compatible with current build environment."
	echo "                 (t18x/t19x under t186ref and t21x under t210ref)"
	echo " -d| --debug     Keep intermediate files during create payload"
	echo ""
	echo "Examples:"
	echo "	${script_name} t21x"
	echo "	(generates bl, kernel, bl_and_kernel,"
	echo "	uboot, porg_qspi, and porg_sd"
	echo "	multi-spec payloads for t21x SoC)"
	echo ""
	echo "	${script_name} t18x"
	echo "	(generates bl, kernel, and bl_and_kernel"
	echo "	multi-spec payloads for t18x SoC)"
	echo ""
	echo "	${script_name} t19x"
	echo "	(generates bl, kernel, and bl_and_kernel"
	echo "	multi-spec payloads for t19x SoC)"
	echo ""
	echo "Notes:"
	echo "	- generates bl_only_payload, kernel_only_payload,"
	echo "	  and bl_update_payload (bl_and_kernel) for t18x and t19x"
	echo "	- also generates uboot_only_payload, porg_qspi_only_payload,"
	echo "	  and porg_sd_only_payload for t21x"
	echo "	- payloads are under \"Linux_for_Tegra/bootloader/payloads_\""
	echo "	  (bl_update_payload contains both bootloader and kernel binaries)"
	echo ""
	echo "These generated payloads are consumed by nv_update_engine on the target"
	echo "to update bootloader and kernel partitions on the device."

	exit 1
}

function check_pre_req()
{
	if [ -z "$1" ]; then
		usage "Error. Arguments required"
	fi

	while [ -n "${1}" ]; do
		case "${1}" in
			-h | --help)
				usage
				;;
			-u)
				[ -n "${2}" ] || usage "Not enough parameters"
				build_bup_script_opts+="-u \"${2}\""
				shift 2
				;;
			t18x)
				target_soc=("${t18x_spec[@]}")
				target_soc_name="t18x"
				shift 1
				;;
			t19x)
				target_soc=("${t19x_spec[@]}")
				target_soc_name="t19x"
				shift 1
				;;
			t21x)
				target_soc=("${t21x_spec[@]}")
				target_soc_name="t21x"
				shift 1
				;;
			-d | --debug)
				dbg_payloads=1
				shift 1
				;;
			*)
				usage "Error. Unknown option or target SoC: ${1}"
				;;
		esac
	done

	if [ ! -f "${build_bup_script}" ]; then
		echo "Error. ${build_bup_script} not found" > /dev/stderr
		usage
	fi
}

function create_payloads()
{
	local ret_msg=""
	local ret_val=0
	local fail_count=0

	local spec_tmp="${target_soc[0]}"
	eval "${spec_tmp}"
	local cmd_clean="FAB=${fab} BOARDID=${boardid} BOARDSKU=${boardsku} \
		BOARDREV=${boardrev} FUSELEVEL=${fuselevel} CHIPREV=${chiprev} \
		${build_bup_script} --clean-up ${board} ${rootdev}"
	if eval "${cmd_clean}"; then
		ret_msg+="\r\nSUCCESS: cleaned up BUP tmp files prior to payload creation"
	else
		ret_msg+="\r\nFAILURE: error cleaning BUP tmp files"
		ret_val=1
		((++fail_count))
	fi

	for spec in "${target_soc[@]}"; do
		eval "${spec}"

		if [ "${fuselevel_s}" == "0" ]; then
			fuselevel="fuselevel_nofuse";
		else
			fuselevel="fuselevel_production";
		fi

		local cmd="FAB=${fab} BOARDID=${boardid} BOARDSKU=${boardsku} \
			BOARDREV=${boardrev} FUSELEVEL=${fuselevel} CHIPREV=${chiprev} \
			${build_bup_script} ${build_bup_script_opts} \
			${board} ${rootdev}"

		echo -e "${cmd}\r\n"
		if eval "${cmd}"; then
			ret_msg+="\r\nSUCCESS: created payload for config \"${spec}\""
		else
			ret_msg+="\r\nFAILURE: no payload made for config \"${spec}\""
			ret_val=1
			((++fail_count))
		fi
	done

	if [ "${dbg_payloads}" -eq 0 ]; then
		if eval "${cmd_clean}"; then
			ret_msg+="\r\nSUCCESS: cleaned up BUP tmp files after payload creation"
		else
			ret_msg+="\r\nFAILURE: error cleaning BUP tmp files"
			ret_val=1
			((++fail_count))
		fi
	fi

	echo "${target_soc_name} payload generation complete with ${fail_count} failure(s)"
	echo -e "${ret_msg}"
	exit "${ret_val}"

}

script_name="$(basename "${0}")"
script_file_name="$(echo "${script_name}" | cut -f 1 -d '.')"
l4t_dir="$(cd "$(dirname "${0}")" && pwd)"
build_bup_script="${l4t_dir}/build_l4t_bup.sh"
build_bup_script_opts="--multi-spec "
target_soc_name=""
dbg_payloads=0

t18x_spec=(
	# jetson-tx2:
	'boardid=3310;fab=B00;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2;rootdev=mmcblk0p1'
	'boardid=3310;fab=B02;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2;rootdev=mmcblk0p1'
	'boardid=3310;fab=C04;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2;rootdev=mmcblk0p1'
	'boardid=3310;fab=D00;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2;rootdev=mmcblk0p1'
	'boardid=3310;fab=D01;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2;rootdev=mmcblk0p1'

	# jetson-tx2-as-4GB:
	'boardid=3310;fab=D00;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2-as-4GB;rootdev=mmcblk0p1'
	'boardid=3310;fab=D01;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2-as-4GB;rootdev=mmcblk0p1'

	# jetson-tx2i:
	'boardid=3489;fab=300;boardsku=;boradrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2i;rootdev=mmcblk0p1'

	# jetson-tx2-4GB:
	'boardid=3489;fab=300;boardsku=;boradrev=;fuselevel_s=1;chiprev=0;board=jetson-tx2-4GB;rootdev=mmcblk0p1'
)
t19x_spec=(
	# jetson-xavier:
	'boardid=2888;fab=400;boardsku=0001;boardrev=H.0;fuselevel_s=1;chiprev=2;board=jetson-xavier;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0001;boardrev=J.0;fuselevel_s=1;chiprev=2;board=jetson-xavier;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0004;boardrev=F.0;fuselevel_s=1;chiprev=2;board=jetson-xavier;rootdev=mmcblk0p1'

	# jetson-xavier-8gb:
	'boardid=2888;fab=400;boardsku=0006;boardrev=B.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-8gb;root=mmcblk0p1'

	# jetson-xavier-as-8gb:
	'boardid=2888;fab=400;boardsku=0001;boardrev=H.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-as-8gb;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0001;boardrev=J.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-as-8gb;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0004;boardrev=F.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-as-8gb;rootdev=mmcblk0p1'

	# jetson-xavier-maxn:
	'boardid=2888;fab=400;boardsku=0001;boardrev=H.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-maxn;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0001;boardrev=J.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-maxn;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0004;boardrev=F.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-maxn;rootdev=mmcblk0p1'

	# jetson-xavier-slvs-ec:
	'boardid=2888;fab=400;boardsku=0001;boardrev=H.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-slvs-ec;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0001;boardrev=J.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-slvs-ec;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0004;boardrev=F.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-slvs-ec;rootdev=mmcblk0p1'

	# jetson-xavier-as-xavier-nx:
	'boardid=2888;fab=400;boardsku=0001;boardrev=H.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-as-xavier-nx;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0001;boardrev=J.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-as-xavier-nx;rootdev=mmcblk0p1'
	'boardid=2888;fab=400;boardsku=0004;boardrev=F.0;fuselevel_s=1;chiprev=2;board=jetson-xavier-as-xavier-nx;rootdev=mmcblk0p1'
)
t21x_spec=(
	# jetson-nano-qspi-sd:
	'boardid=3448;fab=100;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-nano-qspi-sd;rootdev=mmcblk0p1'
	'boardid=3448;fab=200;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-nano-qspi-sd;rootdev=mmcblk0p1'
	'boardid=3448;fab=300;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-nano-qspi-sd;rootdev=mmcblk0p1'

	# jetson-nano-emmc:
	'boardid=3448;fab=200;boardsku=0002;boardrev=;fuselevel_s=1;chiprev=;board=jetson-nano-emmc;rootdev=mmcblk0p1'
	'boardid=3448;fab=300;boardsku=0002;boardrev=;fuselevel_s=1;chiprev=;board=jetson-nano-emmc;rootdev=mmcblk0p1'
	'boardid=3448;fab=400;boardsku=0002;boardrev=;fuselevel_s=1;chiprev=;board=jetson-nano-emmc;rootdev=mmcblk0p1'

	# jetson-tx1:
	'boardid=2180;fab=100;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx1;rootdev=mmcblk0p1'
	'boardid=2180;fab=410;boardsku=;boardrev=;fuselevel_s=1;chiprev=0;board=jetson-tx1;rootdev=mmcblk0p1'
)

echo ""
echo "Generate Multi-Spec BUP Tool"
echo ""

check_pre_req "${@}"
create_payloads
