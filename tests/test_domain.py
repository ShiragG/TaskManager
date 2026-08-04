from taskmanager.domain import make_folder_name, sanitize_for_folder


def test_make_folder_name_basic():
    assert make_folder_name("123", "fix") == "123___fix"


def test_make_folder_name_truncates_long_description():
    long = "a" * 60
    name = make_folder_name("1", long)
    assert name.startswith("1___")
    assert name.endswith("..._")
    assert len(name.split("___", 1)[1]) <= 53


def test_sanitize_strips_forbidden():
    assert ":" not in sanitize_for_folder("a:b/c")
    assert "___" not in sanitize_for_folder("x___y")
