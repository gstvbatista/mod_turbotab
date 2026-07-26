"""
Pacote principal do projeto Mod TurboTables em Python.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("turbotab")
except PackageNotFoundError:
    __version__ = "0.0.0"
