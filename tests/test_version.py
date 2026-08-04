from taskmanager.version import get_version


def test_get_version_is_nonempty():
    version = get_version()
    assert version
    assert version[0].isdigit()
