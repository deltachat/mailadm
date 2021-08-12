import os
import setuptools

def main():
    with open("README.rst") as f:
        long_desc = f.read()

    setuptools.setup(
        name='mailadm',
        description='web API and CLI tool for automatic e-mail user creation/deletion',
        long_description = long_desc,
        setup_requires=['setuptools_scm'],
        use_scm_version = True,
        url='https://github.com/deltachat/mailadm',
        license='GPL',
        platforms=['unix', 'linux'],
        author='holger',
        author_email='holger@merlinux.eu',
        package_dir={'': 'src'},
        packages=setuptools.find_packages('src'),
        package_data={'mailadm': ['data/*.ttf', 'data/*.png', 'data/sysconfig/*']},
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
        install_requires=[
            "click>=6.0",
            "flask",
            "pillow",
            "qrcode",
            "gunicorn",
        ],
        zip_safe=False,
    )

if __name__ == '__main__':
    main()

