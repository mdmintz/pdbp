"""*** pdbp (Pdb+) ***
An advanced console debugger for Python.
Can be used as a drop-in replacement for pdb and pdbpp.
(Python 3.6+)"""
from setuptools import setup, find_packages  # noqa
import os
import sys


this_dir = os.path.abspath(os.path.dirname(__file__))
long_description = None
total_description = None
try:
    with open(os.path.join(this_dir, "README.md"), "rb") as f:
        total_description = f.read().decode("utf-8")
    description_lines = total_description.split("\n")
    long_description_lines = []
    for line in description_lines:
        if not line.startswith("<meta ") and not line.startswith("<link "):
            long_description_lines.append(line)
    long_description = "\n".join(long_description_lines)
except IOError:
    long_description = "pdbp (Pdb+): A drop-in replacement for pdb and pdbpp."

if sys.argv[-1] == "publish":
    reply = None
    input_method = input
    confirm_text = ">>> Confirm release PUBLISH to PyPI? (yes/no): "
    reply = str(input_method(confirm_text)).lower().strip()
    if reply == "yes":
        if sys.version_info < (3, 9):
            print("\nERROR! Publishing to PyPI requires Python>=3.9")
            sys.exit()
        print("\n*** Checking code health with flake8:\n")
        os.system("python -m pip install 'flake8==6.0.0'")
        flake8_status = os.system("flake8 --exclude=.eggs,temp")
        if flake8_status != 0:
            print("\nERROR! Fix flake8 issues before publishing to PyPI!\n")
            sys.exit()
        else:
            print("*** No flake8 issues detected. Continuing...")
        print("\n*** Removing existing distribution packages: ***\n")
        os.system("rm -f dist/*.egg; rm -f dist/*.tar.gz; rm -f dist/*.whl")
        os.system("rm -rf build/bdist.*; rm -rf build/lib")
        print("\n*** Installing build: *** (Required for PyPI uploads)\n")
        os.system("python -m pip install --upgrade 'build>=0.10.0'")
        print("\n*** Installing pkginfo: *** (Required for PyPI uploads)\n")
        os.system("python -m pip install --upgrade 'pkginfo>=1.9.6'")
        print("\n*** Installing readme-renderer: *** (For PyPI uploads)\n")
        os.system("python -m pip install --upgrade 'readme-renderer>=40.0'")
        print("\n*** Installing twine: *** (Required for PyPI uploads)\n")
        os.system("python -m pip install --upgrade 'twine>=4.0.2'")
        print("\n*** Installing tqdm: *** (Required for PyPI uploads)\n")
        os.system("python -m pip install --upgrade tqdm")
        print("\n*** Rebuilding distribution packages: ***\n")
        os.system("python -m build")  # Create new tar/wheel
        print("\n*** Publishing The Release to PyPI: ***\n")
        os.system("python -m twine upload dist/*")  # Requires ~/.pypirc Keys
        print("\n*** The Release was PUBLISHED SUCCESSFULLY to PyPI! :) ***\n")
    else:
        print("\n>>> The Release was NOT PUBLISHED to PyPI! <<<\n")
    sys.exit()

setup(
    name="pdbp",
    version="1.4.1",
    description="pdbp (Pdb+): A drop-in replacement for pdb and pdbpp.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="pdb debugger tab color completion",
    url="https://github.com/mdmintz/pdbp",
    project_urls={
        "Changelog": "https://github.com/mdmintz/pdbp/releases",
        "Download": "https://pypi.org/project/pdbp/#files",
        "Bug Tracker": "https://github.com/mdmintz/pdbp/issues",
        "PyPI": "https://pypi.org/project/pdbp/",
        "Source": "https://github.com/mdmintz/pdbp",
    },
    py_modules=["pdbp"],
    package_dir={"": "src"},
    platforms=["Windows", "Linux", "Mac OS-X"],
    author="Michael Mintz",
    author_email="mdmintz@gmail.com",
    maintainer="Michael Mintz",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: MacOS X",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development",
        "Topic :: Software Development :: Debuggers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: Utilities",
    ],
    python_requires=">=3.6",
    install_requires=[
        'pygments>=2.14.0;python_version<"3.7"',
        'pygments>=2.15.1;python_version>="3.7"',
        "tabcompleter>=1.2.1",
    ],
    setup_requires=[],
    include_package_data=True,
)

print("\n*** pdbp (Pdb+) Installation Complete! ***\n")
