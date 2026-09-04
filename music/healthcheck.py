"""
Health check and readiness verification utility for Music Upscaler Pro.
Can be run standalone: python -m music.healthcheck [--open-browser] [--url URL] [--timeout TIMEOUT]
"""
import sys
import time
import urllib.request
import webbrowser
import argparse


def check_health(url="http://127.0.0.1:8001/api/health/", timeout=2.0):
    """Check if the service is healthy and responding."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MusicUpscaler-HealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 301, 302)
    except Exception:
        return False


def wait_for_server(url="http://127.0.0.1:8001/", timeout=60.0, open_browser=False, verbose=True):
    """
    Poll the health endpoint until the server is ready, then optionally open the browser.
    """
    base_url = url.rstrip('/')
    health_url = f"{base_url}/api/health/"
    start_time = time.time()

    if verbose:
        print(f"[HealthCheck] Waiting for application to initialize at {base_url}...")

    while time.time() - start_time < timeout:
        time.sleep(0.4)
        if check_health(health_url, timeout=1.5) or check_health(base_url, timeout=1.5):
            elapsed = time.time() - start_time
            if verbose:
                print(f"[HealthCheck OK] Server is healthy! (ready in {elapsed:.1f}s)")
            if open_browser:
                if verbose:
                    print(f"[HealthCheck] Opening {base_url} in your default browser...")
                webbrowser.open(base_url)
            return True

    if verbose:
        print(f"[HealthCheck Timeout] Server did not become ready within {timeout}s.")
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Music Upscaler health and readiness.")
    parser.add_argument("--url", default="http://127.0.0.1:8001/", help="Base URL of the application")
    parser.add_argument("--timeout", type=float, default=60.0, help="Maximum seconds to wait")
    parser.add_argument("--open-browser", action="store_true", help="Open browser upon successful health check")
    args = parser.parse_args()

    success = wait_for_server(url=args.url, timeout=args.timeout, open_browser=args.open_browser)
    sys.exit(0 if success else 1)
