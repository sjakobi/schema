"""`schema` lives on `GitHub <http://github.com/halst/schema/>`_."""
from setuptools import setup


setup(
    name = "schema",
    version = "0.1.0",
    author = "Vladimir Keleshev",
    author_email = "vladimir@keleshev.com",
    description = "Simple data validation library",
    license = "MIT",
    keywords = "schema json validation",
    url = "http://github.com/halst/schema",
    py_modules=['schema'],
    long_description=__doc__,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.1",
        "Programming Language :: Python :: 3.2",
        "License :: OSI Approved :: MIT License",
    ],
)