from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Home
    page.goto("http://localhost:8000")
    # Wait for the page to load
    page.wait_for_selector('h1', state='visible')
    page.screenshot(path="verification/01_home.png")

    # History
    page.click("text=History")
    page.wait_for_selector('h1', state='visible')
    page.screenshot(path="verification/02_history.png")

    # Likes
    page.click("text=Likes")
    page.wait_for_selector('h1', state='visible')
    page.screenshot(path="verification/03_likes.png")

    # Account
    page.click("text=Profile") # Use text from sidebar
    page.wait_for_selector('h1', state='visible')
    page.screenshot(path="verification/04_account.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
