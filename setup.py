import os
import setuptools

def main():
    with open(os.path.join("src","mailadm", "__init__.py")) as f:
        for line in f:
            if "__version__" in line.strip():
                version = line.split("=", 1)[1].strip().strip('"')
                break

    with open("README.rst") as f:
        long_desc = f.read()

    setuptools.setup(
        name='mailadm',
        description='testrun.org control program (WIP)',
        long_description = long_desc,
        version=version,
        url='https://github.com/deltachat/playground',
        license='GPL',
        platforms=['unix', 'linux'],
        author='holger',
        author_email='holger@merlinux.eu',
        package_dir={'': 'src'},
        packages = setuptools.find_packages('src'),
        classifiers=['Development Status :: 4 - Beta',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Operating System :: POSIX',
                     'Operating System :: MacOS :: MacOS X',
                     'Topic :: Utilities',
                     'Intended Audience :: Developers',
                     'Programming Language :: Python'],
        entry_points='''
            [console_scripts]
            mailadm=mailadm.cmdline:mailadm_main
        ''',
        install_requires = ["flask", "click>=6.0", "iniconfig>=1.0"],
        zip_safe=False,
    )

if __name__ == '__main__':
    main()

