#!/bin/bash

readonly THIS_SCRIPT="$(basename $0)"
# change this if you extract it somewhere else in the Dockerfile:
readonly L4T_PATH="/Linux_for_Tegra"

set -e
umask 22

function fail_if_not_in_container() {
# https://stackoverflow.com/questions/20010199/how-to-determine-if-a-process-runs-inside-lxc-docker
	if [ ! -f /.dockerenv ] && [ ! "grep 'docker\|lxc' /proc/1/cgroup" ]; then
		>&2 echo "${THIS_SCRIPT} must run in a container"
		exit 1
	fi
}

function fail_if_l4t_not_writable() {
	if [ ! -w "${L4T_PATH}" ]; then
		>&2 echo "${L4T_PATH} is not writable. Please review your Dockerfile."
		exit 1
	fi
}

function fail_if_l4t_world_writable() {
	if [ "$(find "${L4T_PATH}" -perm o+w)" ]; then
		>&2 echo "Some files in ${L4T_PATH} are world writable. Failing."
		# todo: output a list of those files that failed
		exit 1
	fi
}

function apply_patches() {
	patch -p 2 -d "${L4T_PATH}" -i "$1"
}

function main() {
	# parse arguments
	case "${1}" in
		"nano" | "tx1")
			BSP="nano_tx1"
			;;
		"tx2" | "xavier")
			BSP="tx2_xavier"
			;;
		*)
			>&2 echo "board must be nano, tx1, tx2, or xavier"
			show_usage
			exit 1
			;;
	esac

	patch="/patches/${BSP}/patch.diff"

	fail_if_not_in_container
	fail_if_l4t_not_writable
	fail_if_l4t_world_writable

	apply_patches "${patch}"
}

main "${1}"
