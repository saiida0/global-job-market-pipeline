import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = PROJECT_ROOT / "dashboard" / "app.py"


def test_navigation_pages_use_existing_absolute_file_paths():
    tree = ast.parse(APP_FILE.read_text(encoding="utf-8"))
    page_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
        and node.func.attr == "Page"
    ]

    assert len(page_calls) == 2
    expected_titles = {"Market Overview", "Skill Match"}
    actual_titles = set()

    for page_call in page_calls:
        path_argument = page_call.args[0]
        assert isinstance(path_argument, ast.Call)
        assert isinstance(path_argument.func, ast.Name)
        assert path_argument.func.id == "str"

        path_expression = path_argument.args[0]
        assert isinstance(path_expression, ast.BinOp)
        assert isinstance(path_expression.op, ast.Div)
        assert isinstance(path_expression.left, ast.Name)
        assert path_expression.left.id == "DASHBOARD_DIR"
        assert isinstance(path_expression.right, ast.Constant)

        page_path = (APP_FILE.parent / path_expression.right.value).resolve()
        assert page_path.is_absolute()
        assert page_path.is_file()

        title = next(
            keyword.value.value
            for keyword in page_call.keywords
            if keyword.arg == "title"
            and isinstance(keyword.value, ast.Constant)
        )
        actual_titles.add(title)

    assert actual_titles == expected_titles
