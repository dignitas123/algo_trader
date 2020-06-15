import setuptools
from os.path import dirname, join

here = dirname(__file__)


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="algo-trader",
    version="0.1.1",
    author="Niclas Hummel",
    author_email="niclashummel.fx@gmail.com",
    description="Trade execution engine to process API data and transmit"
    " orders to Bitmex and other brokers.",
    long_description=open(join(here, 'README.md')).read(),
    long_description_content_type='text/markdown',
    url="https://github.com/dignitas123/algo_trader",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        ],
    python_requires='>=3.6',
)
