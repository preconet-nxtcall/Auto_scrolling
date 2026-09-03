import os
import time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

def create_sample_image(filepath: Path):
    """Creates a sample test PNG image."""
    img = Image.new("RGB", (600, 800), color=(79, 70, 229))
    img.save(filepath, format="PNG")

def run_playwright_e2e_test():
    test_dir = Path(__file__).parent
    sample_file = test_dir / "sample_playwright_test.png"
    create_sample_image(sample_file)

    screenshot_dir = Path("C:/Users/dell/.gemini/antigravity-ide/brain/cf5deff8-9cc1-4386-a33c-c6e87384495c")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / "autoscroll_playwright_test.png"

    print("[Playwright] Starting Playwright E2E Browser Test on http://127.0.0.1:8000 ...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False)
        except Exception:
            browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # 1. Navigate to application dashboard
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        print("[Playwright] Dashboard loaded successfully.")

        # 2. Upload sample document
        file_input = page.locator("#fileInput")
        file_input.set_input_files(str(sample_file))
        print("[Playwright] Sample document attached to upload dropzone.")

        # 3. Wait for conversion to complete and Ready status badge
        page.wait_for_selector(".status-ready", timeout=15000)
        print("[Playwright] Document status updated to 'Ready'.")

        # 4. Click the 'Preview' button
        preview_btn = page.locator("button:has-text('Preview')").first
        preview_btn.click()
        print("[Playwright] Clicked 'Preview' button.")

        # 5. Verify that #viewerOverlay is now visible and not hidden by d-none
        overlay = page.locator("#viewerOverlay")
        page.wait_for_selector("#viewerOverlay:not(.d-none)", timeout=5000)
        assert overlay.is_visible(), "Error: #viewerOverlay is not visible on screen!"
        print("[Playwright] SUCCESS: #viewerOverlay is visible on screen!")

        # 6. Verify page progress indicator and PDF page wrapper creation
        page.wait_for_selector(".pdf-page-wrapper", timeout=10000)
        print("[Playwright] PDF.js page wrapper containers created successfully.")

        # 7. Wait 2.5 seconds to observe auto-scrolling progress
        time.sleep(2.5)

        # 8. Capture proof screenshot
        page.screenshot(path=str(screenshot_path))
        print(f"[Playwright] Captured proof screenshot at: {screenshot_path}")

        # 9. Test closing the viewer overlay
        exit_btn = page.locator("#exitViewerBtn")
        exit_btn.click()
        page.wait_for_selector("#viewerOverlay.d-none", timeout=5000)
        print("[Playwright] Viewer overlay closed cleanly upon clicking exit.")

        browser.close()

    if sample_file.exists():
        sample_file.unlink()

    print("[Playwright] Playwright E2E test completed with 100% success!")

if __name__ == "__main__":
    run_playwright_e2e_test()
