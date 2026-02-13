"""Upload local images to Facebook Attachment Upload API and save mapping.

Usage:
    cd webhook && python upload_images.py

This script:
1. Reads storage/image_mapping.txt for the list of image IDs and files
2. Uploads each image to Facebook via the Attachment Upload API (multipart form)
3. Saves the resulting attachment_ids to webhook/fb_attachment_ids.json

Prerequisites:
- FB_PAGE_ACCESS_TOKEN must be set in webhook/.env
- Images must exist in storage/image/

Facebook Attachment Upload API:
    POST https://graph.facebook.com/v24.0/me/message_attachments
    Content-Type: multipart/form-data
    Body:
        message={"attachment":{"type":"image","payload":{"is_reusable":true}}}
        filedata=@path/to/image.jpg
    Params:
        access_token=PAGE_ACCESS_TOKEN

    Response: {"attachment_id": "1234567890"}
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_API_URL = "https://graph.facebook.com/v24.0/me/message_attachments"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
IMAGE_DIR = STORAGE_DIR / "image"
IMAGE_MAPPING_PATH = STORAGE_DIR / "image_mapping.txt"
OUTPUT_PATH = Path(__file__).parent / "fb_attachment_ids.json"


def upload_image(filepath: Path) -> str | None:
    """Upload a single image to Facebook and return the attachment_id."""
    message_json = json.dumps({
        "attachment": {
            "type": "image",
            "payload": {"is_reusable": True}
        }
    })

    with open(filepath, "rb") as f:
        files = {"filedata": (filepath.name, f, "image/jpeg")}
        data = {"message": message_json}

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                GRAPH_API_URL,
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                data=data,
                files=files,
            )

    if resp.status_code == 200:
        return resp.json().get("attachment_id")
    else:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        return None


def main() -> None:
    if not FB_PAGE_ACCESS_TOKEN:
        print("Error: FB_PAGE_ACCESS_TOKEN not set in .env")
        sys.exit(1)

    if not IMAGE_MAPPING_PATH.exists():
        print(f"Error: Image mapping not found at {IMAGE_MAPPING_PATH}")
        sys.exit(1)

    # Load image mapping
    with open(IMAGE_MAPPING_PATH, "r", encoding="utf-8") as f:
        image_mapping = json.load(f)

    print(f"Found {len(image_mapping)} images to upload\n")

    # Load existing mapping if available (for resume support)
    existing_ids: dict[str, str] = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing_ids = json.load(f)
        print(f"Found existing mapping with {len(existing_ids)} entries (will skip these)\n")

    attachment_ids = dict(existing_ids)
    uploaded = 0
    skipped = 0
    failed = 0

    for image_id, info in image_mapping.items():
        # Skip if already uploaded
        if image_id in existing_ids:
            print(f"  SKIP {image_id}: already uploaded (attachment_id={existing_ids[image_id][:20]}...)")
            skipped += 1
            continue

        filepath = IMAGE_DIR / info["file"]
        if not filepath.exists():
            print(f"  SKIP {image_id}: file not found at {filepath}")
            failed += 1
            continue

        print(f"  Uploading {image_id} ({info['file']})...", end=" ", flush=True)
        att_id = upload_image(filepath)

        if att_id:
            attachment_ids[image_id] = att_id
            print(f"OK -> attachment_id={att_id}")
            uploaded += 1
        else:
            print("FAILED")
            failed += 1

    # Save mapping
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(attachment_ids, f, indent=2, ensure_ascii=False)

    print(f"\n{'═' * 50}")
    print(f"Uploaded: {uploaded}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")
    print(f"Total in mapping: {len(attachment_ids)}/{len(image_mapping)}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
