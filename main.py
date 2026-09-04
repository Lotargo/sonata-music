import os
import sys
import threading


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Auto-migrate if this is the main entry point and no args provided
    if len(sys.argv) == 1:
        print("Running database migrations...")
        execute_from_command_line(['manage.py', 'migrate'])

        print("Checking media integrity...")
        execute_from_command_line(['manage.py', 'cleanup_missing_media'])

        print("\nStarting development server...")
        print("Waiting for server to become healthy before opening browser...\n")

        if not os.environ.get('STUDIO_HEALTHCHECK_ACTIVE') and os.environ.get('RUN_MAIN') != 'true':
            try:
                from music.healthcheck import wait_for_server
                threading.Thread(
                    target=wait_for_server,
                    kwargs={'url': 'http://127.0.0.1:8001/', 'open_browser': True},
                    daemon=True
                ).start()
            except ImportError:
                pass

        # Change default port to 8001 to avoid conflicts
        sys.argv.append('runserver')
        sys.argv.append('127.0.0.1:8001')

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

