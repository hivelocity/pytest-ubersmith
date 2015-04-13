#!/usr/bin/env python
import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


setup(
    name='pytest-ubersmith',
    author='Zach Kanzler',
    author_email='zkanzler@hivelocity.net',
    url='https://github.com/hivelocity/pytest-ubersmith',
    version='1.0.1',
    description='Easily mock calls to ubersmith at the `requests` level.',
    long_description=open('README.rst').read().strip(),
    license='MIT License',
    install_requires=[
        'pytest>=2.6.0',
        'ubersmith>=0.3.0',
        'requests-mock>=0.6.0',
    ],
    cmdclass={'test': PyTest},
    py_modules=['pytest_ubersmith'],
    entry_points={'pytest11': ['pytest_ubersmith = pytest_ubersmith']},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Testing',
    ]
)
