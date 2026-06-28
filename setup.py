"""Recordly — 开源屏幕录制与回放工具"""
from setuptools import find_packages, setup

setup(
    name="recordly",
    version="1.0.0",
    description="开源屏幕录制与回放工具",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="devcxl",
    author_email="64475363+devcxl@users.noreply.github.com",
    url="https://github.com/devcxl/recordly",
    license="MIT",
    packages=find_packages(),
    package_data={
        "resources": ["icons/*"],
    },
    python_requires=">=3.10",
    install_requires=[
        "PyQt5>=5.15",
        "numpy>=1.20",
        "Pillow>=9.0",
        "mss>=5.0",
        "pynput>=1.7",
        "sounddevice>=0.4",
    ],
    extras_require={
        "test": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "recordly=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics :: Capture :: Screen Capture",
    ],
)
