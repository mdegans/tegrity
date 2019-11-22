import os

import setuptools

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_DIR, 'README.md')) as readme:
    long_description = readme.read()

setuptools.setup(
    name='tegrity',
    version='0.0.1',
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
    entry_points={
        'console_scripts': ['tegrity=tegrity.__main__:cli_main']
    },
    author='Michael de Gans',
    author_email='michael.john.degans@gmail.com',
    project_urls={
        'Bug Reports': 'https://github.com/mdegans/tegrity/issues',
        'Source': 'https://github.com/mdegans/tegrity/',
    },
)
