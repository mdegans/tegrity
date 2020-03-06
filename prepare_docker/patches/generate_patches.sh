#!/bin/bash

# https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
readonly THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
readonly SOURCE_DIRS=("nano_tx1" "tx2_xavier")

set -e

function generate_patches() {
	for board in "${SOURCE_DIRS[@]}"
	do
		echo "generating patches for ${board}"
		pushd "${THIS_DIR}/${board}" > /dev/null
		set +e
		diff -rub "./originals" "./modified" > "./patch.diff"
		if [ $? -eq 2 ]; then
			>&2 echo "Diff failed. Patch could not be created."
			exit 1
		fi
		set -e
		popd > /dev/null
	done
}

generate_patches