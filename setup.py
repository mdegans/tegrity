import os

import setuptools

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_DIR, 'README.md')) as readme:
    long_description = readme.read()

setuptools.setup(
    name='tegrity',
    version='0.0.3',
    description='Helps bake system images for NVIDIA Tegra',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',

        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    python_requires='>=3.6',
    install_requires=None,
    packages=['tegrity'],
    package_data={
        'tegrity': [
            'tegrity-firstboot.service.in',
            'tegrity-firstboot.service.in.LICENSE.txt',
            'tegrity-service-simple.service.in',
        ]
    },
    entry_points={
        'console_scripts': [
            # 'tegrity-apt=tegrity.apt:cli_main',
            # 'tapt=tegrity.apt:cli_main',
            'tegrity-image=tegrity.image:cli_main',
            'tegrity-qemu=tegrity.qemu:cli_main',
            'tegrity-rootfs=tegrity.rootfs:cli_main',
            'tegrity-kernel=tegrity.kernel:cli_main',
            'tegrity-toolchain=tegrity.toolchain:cli_main',
            'tegrity=tegrity.__main__:cli_main',
        ]
    },
    author='Michael de Gans',
    author_email='michael.john.degans@gmail.com',
    project_urls={
        'Bug Reports': 'https://github.com/mdegans/tegrity/issues',
        'Source': 'https://github.com/mdegans/tegrity/',
    },
)
