from pathlib import Path
from unittest.mock import patch
from chroma_ops.utils import check_disk_space, get_disk_free_space, get_dir_size


def test_check_disk_space() -> None:
    with patch("chroma_ops.utils.get_dir_size") as mock_dir_size, patch(
        "chroma_ops.utils.get_disk_free_space"
    ) as mock_free_space:
        # Enough space available
        mock_dir_size.return_value = 1000  # 1KB source
        mock_free_space.return_value = 10000  # 10KB free
        assert check_disk_space("/fake/source", "/fake/target") is True

        # Not enough space
        mock_dir_size.return_value = 1000  # 1KB source
        mock_free_space.return_value = 1000  # 1KB free (less than 1.1x required)
        assert check_disk_space("/fake/source", "/fake/target") is False

        # Exactly at the threshold
        mock_dir_size.return_value = 1000  # 1KB source
        mock_free_space.return_value = 1100  # 1.1KB free (exactly 1.1x)
        assert check_disk_space("/fake/source", "/fake/target") is True


def test_get_disk_free_space(tmp_path: Path) -> None:
    # Test with actual filesystem
    free_space = get_disk_free_space(str(tmp_path))
    assert isinstance(free_space, int)
    assert free_space > 0


def test_get_dir_size(tmp_path: Path) -> None:
    # Create a test file with known size
    test_file = tmp_path / "test.txt"
    test_content = "x" * 1000  # 1KB of data
    test_file.write_text(test_content)

    dir_size = get_dir_size(str(tmp_path))
    assert isinstance(dir_size, int)
    assert dir_size >= 1000  # Should be at least as large as our test file
