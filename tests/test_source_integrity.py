import ast
from collections import Counter
from pathlib import Path


def test_cli_dict_literals_have_no_duplicate_string_keys():
    path = Path(__file__).parents[1] / "src" / "hlp" / "cli.py"
    tree = ast.parse(path.read_text())

    duplicates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
        ]
        repeated = sorted(
            key for key, count in Counter(keys).items()
            if count > 1
        )
        if repeated:
            duplicates.append((node.lineno, repeated))

    assert not duplicates, duplicates
