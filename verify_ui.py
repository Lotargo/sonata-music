import os
import time
from playwright.sync_api import sync_playwright, expect

def run():
    os.makedirs("/home/jules/verification", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        try:
            print("Navigating to home...")
            page.goto("http://127.0.0.1:8001")

            # Wait for title or sidebar
            expect(page).to_have_title("Music Platform")
            print("Home page loaded.")

            # Screenshot Home
            page.screenshot(path="/home/jules/verification/home.png")
            print("Home screenshot saved.")

            # Click Upload
            print("Clicking Upload Track...")
            # Use a robust selector. The button in header has text "Upload Track"
            page.get_by_role("button", name="Upload Track").first.click()

            # Wait for modal to appear
            # The modal has id "upload-modal" and removes "hidden" class
            modal = page.locator("#upload-modal")
            expect(modal).to_be_visible()

            # Wait for transition (simple wait)
            page.wait_for_timeout(500)

            print("Modal opened.")

            # Screenshot Modal
            page.screenshot(path="/home/jules/verification/verification.png")
            print("Verification screenshot saved.")

        except Exception as e:
            print(f"Error: {e}")
            # Save screenshot even on error if possible
            try:
                page.screenshot(path="/home/jules/verification/error.png")
            except:
                pass
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    run()
