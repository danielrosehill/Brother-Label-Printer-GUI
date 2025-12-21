#!/usr/bin/env python3
"""Setup script for Brother Label Printer"""

from setuptools import setup, find_packages

setup(
    name="brother-label-printer",
    version="1.2.0",
    description="Label printer GUI for Brother QL-700",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Daniel Rosehill",
    author_email="public@danielrosehill.com",
    url="https://github.com/danielrosehill/brother-ql-label-printer",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "Pillow",
        "qrcode",
        "PyQt6",
        "brother-ql",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Printing",
    ],
)
