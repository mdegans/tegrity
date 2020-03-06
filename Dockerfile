#Copyright 2019 Michael de Gans
#
#Permission is hereby granted, free of charge, to any person obtaining a copy of
#this software and associated documentation files (the "Software"), to deal in
#the Software without restriction, including without limitation the rights to
#use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
#of the Software, and to permit persons to whom the Software is furnished to do
#so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

# This Dockerfile works with rootless Docker!
# https://docs.docker.com/engine/security/rootless/

FROM ubuntu:bionic

# change board here (nano, tx1, tx2, xavier):
# only nano devkit supported for now
ARG BOARD="nano"

# install dependencise and stuff to be owned as root/fake root
RUN apt-get update && apt-get install -y --no-install-recommends \
		bc \
		build-essential \
		ca-certificates \
		lbzip2 \
		libncurses5-dev \
		proot \
		python \
		python3-setuptools \
		qemu-user-static \
		wget

# get the Linux_for_Tegra folder
COPY prepare_docker/scripts /scripts
RUN /scripts/get_bsp.sh $BOARD

# add a regular user to modify the rootfs, but nothing else
RUN adduser \
		--disabled-login \
		--disabled-password \
		--group \
		--no-create-home \
		--system \
		tegrity \
	&& chown -R tegrity:tegrity /Linux_for_Tegra/rootfs
# drop caps to the regular user, get rootfs, and cd to Linux_for_Tegra
USER tegrity:tegrity
RUN /scripts/get_rootfs.sh

# install tegrity systemwide and immutable
USER root:root
WORKDIR /tegrity
COPY tegrity /tegrity/tegrity
COPY setup.py /tegrity
COPY README.md /tegrity
RUN python3 /tegrity/setup.py install && rm -rf /tegrity

WORKDIR /Linux_for_Tegra
# apply user mode patches to Linux_for_Tegra scripts
# todo: move this above when patches finished, since rootfs takes a while to dl
COPY prepare_docker/patches /patches
RUN /patches/apply_patches.sh $BOARD
# record the board build argument so some tegrity functions can autodetect the
# board without using sdkm.db
RUN echo $BOARD > /Linux_for_Tegra/.board
USER tegrity:tegrity
RUN ./apply_binaries.sh
# patches apt sources <SOC> based on .board
RUN tapt --nvidia-ota ./rootfs
# where system images get put:
VOLUME /out

# use tegrity as an entrypoint,