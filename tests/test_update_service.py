from taskmanager.services.update_service import (
    ReleaseAsset,
    LatestRelease,
    asset_name_for_platform,
    parse_release_payload,
    parse_version,
    pick_asset,
    version_is_newer,
)


def test_parse_version():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("0.1.0") == (0, 1, 0)
    assert parse_version("v2") == (2, 0, 0)


def test_version_is_newer():
    assert version_is_newer("v0.2.0", "0.1.0")
    assert not version_is_newer("v0.1.0", "0.1.0")
    assert not version_is_newer("v0.0.9", "0.1.0")


def test_asset_name_for_platform():
    assert asset_name_for_platform("Linux") == "TaskManager"
    assert asset_name_for_platform("Windows") == "TaskManager.exe"
    assert asset_name_for_platform("win32") == "TaskManager.exe"


def test_parse_release_and_pick_asset():
    payload = {
        "tag_name": "v1.4.0",
        "assets": [
            {
                "name": "TaskManager",
                "browser_download_url": "https://example.com/TaskManager",
                "size": 10,
            },
            {
                "name": "TaskManager.exe",
                "browser_download_url": "https://example.com/TaskManager.exe",
                "size": 11,
            },
        ],
    }
    release = parse_release_payload(payload)
    assert release.tag == "v1.4.0"
    assert release.version == "1.4.0"
    linux = pick_asset(release.assets, "TaskManager")
    assert linux is not None
    assert linux.download_url.endswith("/TaskManager")
    win = pick_asset(release.assets, "TaskManager.exe")
    assert win is not None
    assert isinstance(win, ReleaseAsset)


def test_latest_release_dataclass():
    release = LatestRelease(
        tag="v1.0.0",
        version="1.0.0",
        assets=[ReleaseAsset("TaskManager", "https://x/y", 1)],
    )
    assert release.assets[0].name == "TaskManager"
