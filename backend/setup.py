from setuptools import setup, find_packages

setup(
    name="supa-search-backend",
    version="0.1.0",
    packages=find_packages(),
    py_modules=["main", "models", "indexer"],
)
