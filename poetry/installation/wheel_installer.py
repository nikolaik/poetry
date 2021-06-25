import os
import platform
import sys

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Union

from installer.destinations import SchemeDictionaryDestination as BaseDestination

from poetry import __version__
from poetry.utils._compat import WINDOWS


if TYPE_CHECKING:
    from typing import BinaryIO

    from installer.records import RecordEntry
    from installer.utils import Scheme

    from poetry.utils.env import Env


class WheelDestination(BaseDestination):
    def write_to_fs(
        self, scheme: "Scheme", path: Union[Path, str], stream: "BinaryIO"
    ) -> "RecordEntry":
        from installer.records import Hash
        from installer.records import RecordEntry
        from installer.utils import copyfileobj_with_hashing

        target_path = os.path.join(self.scheme_dict[scheme], path)
        if os.path.exists(target_path):
            # Contrary to the base library we don't raise an error
            # here since it can break namespace packages (like Poetry's)
            pass

        parent_folder = os.path.dirname(target_path)
        if not os.path.exists(parent_folder):
            os.makedirs(parent_folder)

        with open(target_path, "wb") as f:
            hash_, size = copyfileobj_with_hashing(stream, f, self.hash_algorithm)

        return RecordEntry(path, Hash(self.hash_algorithm, hash_), size)

    def for_source(self, source: WheelFile) -> "WheelDestination":
        scheme_dict = self.scheme_dict.copy()

        scheme_dict["headers"] = os.path.join(
            scheme_dict["headers"], source.distribution
        )

        return self.__class__(
            scheme_dict, interpreter=self.interpreter, script_kind=self.script_kind
        )


class WheelInstaller:
    def __init__(self, env: "Env") -> None:
        self._env = env

        if not WINDOWS:
            script_kind = "posix"
        else:
            if platform.uname()[4].startswith("arm"):
                script_kind = "win-arm64" if sys.maxsize > 2 ** 32 else "win-arm"
            else:
                script_kind = "win-amd64" if sys.maxsize > 2 ** 32 else "win-ia32"

        schemes = self._env.paths
        schemes["headers"] = schemes["include"]

        self._destination = WheelDestination(
            schemes, interpreter=self._env.python, script_kind=script_kind
        )

    def install(self, wheel: Path) -> None:
        from installer import install
        from installer.sources import WheelFile

        with WheelFile.open(wheel.as_posix()) as source:
            install(
                source=source,
                destination=self._destination.for_source(source),
                # Additional metadata that is generated by the installation tool.
                additional_metadata={
                    "INSTALLER": f"Poetry {__version__}".encode(),
                },
            )