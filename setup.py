from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="bftdetector",
    version="1.0.0",
    author="jspaper22",
    author_email="author@example.com",
    description="Business Flow Tampering Detector",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jspaper22/bftdetector",
    packages=find_packages(include=['bftdetector', 'bftdetector.*']),
    python_requires='>=3',
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Ubuntu 20.04 LTS",
    ],
    include_package_data=True,
    install_requires=[
        'networkx==2.8',
        'bs4==0.0.1',
        'graphviz==0.20',
        'scikit-image==0.19.2',
        'psutil==5.9.0',
        'mmh3==3.0.0',
        'pyhash==0.9.3',
        'imbalanced-learn==0.9.0',
        'Pillow==9.1.0',
    ],
)