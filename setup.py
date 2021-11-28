import setuptools
from os.path import dirname, join

here = dirname(__file__)


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="algo-trader",
    version="2.0.3",
    author="Niclas Hummel",
    author_email="info@algoinvest.online",
    description="Trade execution engine to process API data and transmit"
    " orders to Bitmex and other brokers.",
    long_description=open(join(here, 'README.md')).read(),
    long_description_content_type='text/markdown',
    url="https://github.com/dignitas123/algo_trader",
    install_requires=['bitmex'],
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        'console_scripts': [
            'algotrader=algo_trader.startbot:run',
        ],
    }
)
