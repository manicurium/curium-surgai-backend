#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import threading
from extractor import MultiDeviceVideoSubscriber  # Import the extractor

def start_extractor():
    """Start the MultiDeviceVideoSubscriber in a background thread"""
    subscriber = MultiDeviceVideoSubscriber(
        broker_address="localhost",
        broker_port=1883,
        topic="video/stream",
        base_output_folder="received_frames",
        username="admin",
        password="letmein",
    )
    subscriber.start()

def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "curium_surgai_backend.settings")

    # Check if the command is 'runserver' before starting the extractor
    if 'runserver' in sys.argv:
        extractor_thread = threading.Thread(target=start_extractor)
        extractor_thread.daemon = True
        extractor_thread.start()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
