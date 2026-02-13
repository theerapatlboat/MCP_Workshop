"""Tests for webhook/upload_images.py — Facebook image upload utility.

Covers:
  - upload_image (success, failure, response parsing)
  - main function (loading mapping, resume support, file not found, token missing)
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WEBHOOK_DIR = PROJECT_ROOT / "webhook"

_webhook_str = str(WEBHOOK_DIR)
if _webhook_str in sys.path:
    sys.path.remove(_webhook_str)
sys.path.insert(0, _webhook_str)

_project_str = str(PROJECT_ROOT)
if _project_str not in sys.path:
    sys.path.insert(0, _project_str)

import upload_images
from upload_images import upload_image, main, GRAPH_API_URL


# ===================================================================
# upload_image
# ===================================================================
class TestUploadImage:
    """Tests for the single-image upload function."""

    def test_upload_success_returns_attachment_id(self, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"attachment_id": "att_12345"}

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            result = upload_image(img_file)

        assert result == "att_12345"

    def test_upload_failure_returns_none(self, tmp_path):
        img_file = tmp_path / "bad.jpg"
        img_file.write_bytes(b"\xff\xd8" + b"\x00" * 50)

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "Invalid image"}'

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            result = upload_image(img_file)

        assert result is None

    def test_upload_sends_correct_url(self, tmp_path):
        img_file = tmp_path / "photo.jpg"
        img_file.write_bytes(b"\xff" * 50)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"attachment_id": "att_999"}

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            upload_image(img_file)

        assert instance.post.call_args.args[0] == GRAPH_API_URL

    def test_upload_sends_access_token(self, tmp_path, monkeypatch):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token-abc")
        img_file = tmp_path / "photo.jpg"
        img_file.write_bytes(b"\xff" * 50)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"attachment_id": "att_111"}

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            upload_image(img_file)

        call_kwargs = instance.post.call_args.kwargs
        assert call_kwargs["params"]["access_token"] == "test-token-abc"

    def test_upload_sends_multipart_data(self, tmp_path):
        img_file = tmp_path / "img.jpg"
        img_file.write_bytes(b"\xff\xd8\xff" * 10)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"attachment_id": "att_222"}

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            upload_image(img_file)

        call_kwargs = instance.post.call_args.kwargs
        # Check that 'data' contains the message JSON
        assert "data" in call_kwargs
        msg_data = json.loads(call_kwargs["data"]["message"])
        assert msg_data["attachment"]["type"] == "image"
        assert msg_data["attachment"]["payload"]["is_reusable"] is True
        # Check files parameter
        assert "files" in call_kwargs

    def test_upload_uses_timeout_30(self, tmp_path):
        img_file = tmp_path / "img.jpg"
        img_file.write_bytes(b"\xff" * 10)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"attachment_id": "att_333"}

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            upload_image(img_file)

        # httpx.Client(timeout=30)
        assert mock_httpx_mod.Client.call_args.kwargs.get("timeout") == 30

    def test_upload_response_missing_attachment_id(self, tmp_path):
        img_file = tmp_path / "img.jpg"
        img_file.write_bytes(b"\xff" * 10)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # No attachment_id key

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            result = upload_image(img_file)

        assert result is None

    def test_upload_500_error_returns_none(self, tmp_path):
        img_file = tmp_path / "img.jpg"
        img_file.write_bytes(b"\xff" * 10)

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch.object(upload_images, "httpx") as mock_httpx_mod:
            instance = MagicMock()
            instance.post.return_value = mock_resp
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            mock_httpx_mod.Client.return_value = instance

            result = upload_image(img_file)

        assert result is None


# ===================================================================
# main function
# ===================================================================
class TestMain:
    """Tests for the main() orchestration function."""

    def test_missing_token_exits(self, monkeypatch):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "")
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_missing_mapping_file_exits(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", tmp_path / "nonexistent.txt")
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_uploads_new_images(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        # Create image mapping file
        mapping = {
            "IMG_001": {"file": "product1.jpg", "name": "Product 1"},
            "IMG_002": {"file": "product2.jpg", "name": "Product 2"},
        }
        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        # Create image files
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "product1.jpg").write_bytes(b"\xff" * 100)
        (image_dir / "product2.jpg").write_bytes(b"\xff" * 100)
        monkeypatch.setattr(upload_images, "IMAGE_DIR", image_dir)

        # Output path
        output_file = tmp_path / "fb_attachment_ids.json"
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            mock_upload.side_effect = ["att_001", "att_002"]
            main()

        assert mock_upload.call_count == 2
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result["IMG_001"] == "att_001"
        assert result["IMG_002"] == "att_002"

    def test_skips_already_uploaded(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        mapping = {
            "IMG_001": {"file": "product1.jpg"},
            "IMG_002": {"file": "product2.jpg"},
        }
        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "product2.jpg").write_bytes(b"\xff" * 100)
        monkeypatch.setattr(upload_images, "IMAGE_DIR", image_dir)

        # Existing mapping (IMG_001 already uploaded)
        output_file = tmp_path / "fb_attachment_ids.json"
        output_file.write_text(json.dumps({"IMG_001": "existing_att"}), encoding="utf-8")
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            mock_upload.return_value = "att_002_new"
            main()

        # Should only upload IMG_002
        assert mock_upload.call_count == 1
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result["IMG_001"] == "existing_att"  # preserved
        assert result["IMG_002"] == "att_002_new"

    def test_skips_missing_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        mapping = {"IMG_001": {"file": "missing.jpg"}}
        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        monkeypatch.setattr(upload_images, "IMAGE_DIR", image_dir)

        output_file = tmp_path / "fb_attachment_ids.json"
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            main()

        mock_upload.assert_not_called()
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(result) == 0

    def test_handles_upload_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        mapping = {"IMG_001": {"file": "product1.jpg"}}
        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "product1.jpg").write_bytes(b"\xff" * 100)
        monkeypatch.setattr(upload_images, "IMAGE_DIR", image_dir)

        output_file = tmp_path / "fb_attachment_ids.json"
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            mock_upload.return_value = None  # Failure
            main()

        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert "IMG_001" not in result

    def test_no_existing_mapping_file(self, monkeypatch, tmp_path):
        """When no existing fb_attachment_ids.json exists, starts fresh."""
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        mapping = {"IMG_001": {"file": "product1.jpg"}}
        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "product1.jpg").write_bytes(b"\xff" * 100)
        monkeypatch.setattr(upload_images, "IMAGE_DIR", image_dir)

        output_file = tmp_path / "fb_attachment_ids.json"
        # Do NOT create output_file — simulating first run
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            mock_upload.return_value = "att_fresh"
            main()

        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result["IMG_001"] == "att_fresh"

    def test_saves_output_as_json(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        mapping = {"IMG_001": {"file": "product1.jpg"}}
        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "product1.jpg").write_bytes(b"\xff" * 100)
        monkeypatch.setattr(upload_images, "IMAGE_DIR", image_dir)

        output_file = tmp_path / "fb_attachment_ids.json"
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            mock_upload.return_value = "att_001"
            main()

        # Verify the file is valid JSON with proper formatting
        content = output_file.read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, dict)
        # Verify indentation (indent=2)
        assert "  " in content

    def test_empty_mapping(self, monkeypatch, tmp_path):
        monkeypatch.setattr(upload_images, "FB_PAGE_ACCESS_TOKEN", "test-token")

        mapping_file = tmp_path / "image_mapping.txt"
        mapping_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(upload_images, "IMAGE_MAPPING_PATH", mapping_file)

        output_file = tmp_path / "fb_attachment_ids.json"
        monkeypatch.setattr(upload_images, "OUTPUT_PATH", output_file)

        with patch.object(upload_images, "upload_image") as mock_upload:
            main()

        mock_upload.assert_not_called()
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result == {}


# ===================================================================
# Module-level constants
# ===================================================================
class TestModuleConstants:
    """Tests for module-level constants and paths."""

    def test_graph_api_url(self):
        assert GRAPH_API_URL == "https://graph.facebook.com/v24.0/me/message_attachments"

    def test_project_root_exists(self):
        assert upload_images.PROJECT_ROOT.exists()

    def test_output_path_is_in_webhook_dir(self):
        assert upload_images.OUTPUT_PATH.parent == WEBHOOK_DIR
        assert upload_images.OUTPUT_PATH.name == "fb_attachment_ids.json"

    def test_image_mapping_path(self):
        assert upload_images.IMAGE_MAPPING_PATH.name == "image_mapping.txt"
