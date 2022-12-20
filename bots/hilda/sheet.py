from collections import defaultdict
from dataclasses import dataclass

# TODO: Refactor.


@dataclass
class Sheet:
    """A stylesheet of sorts that can define formatting for strings.

    The format for a sheet is as follows:
    @command_name:
    formatting
        can be indented, but will be stripped!

    @second_command:
    yay

    @third: not allowed on same line :("""

    _inner: dict[str, str]

    @staticmethod
    def from_file(path: str) -> "Sheet":
        """Load a format sheet from a file."""
        with open(path) as f:
            lines: list[str] = f.readlines()
        name: str = ""
        inner: dict[str, str] = defaultdict(lambda: "")
        for line in lines:
            line: str = line.strip()
            if line.startswith("@") and line.endswith(":"):
                name = line[1:-1]
                continue
            inner[name] += line.strip() + "\n"
        return Sheet({k: v.strip() for k, v in inner.items()})

    def __getitem__(self, key: str) -> str:
        return self._inner[key]
