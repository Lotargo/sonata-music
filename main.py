import os
import sys

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

        print("\nStarting development server...")
        print("Open http://127.0.0.1:8001/ in your browser.\n")

        # Change default port to 8001 to avoid conflicts
        sys.argv.append('runserver')
        sys.argv.append('127.0.0.1:8001')

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
