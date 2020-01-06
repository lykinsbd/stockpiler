import setuptools
from stockpiler import __version__

setuptools.setup(
    name="stockpiler",
    setup_requires=[
        "setuptools>=30.3",
    ],
    test_suite="stockpiler.unit_tests",
    version=__version__,
)
