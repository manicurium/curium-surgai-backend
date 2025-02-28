#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

import threading
from surgai_listener import MQTTHandler
from django.conf import settings
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

logger = logging.getLogger()

logger.setLevel(logging.DEBUG)


def start_extractor():
    """Start the MultiDeviceVideoSubscriber in a background thread"""
    subscriber = MQTTHandler(
        broker_address="azurecpu1.curium.life",
        broker_port=1883,
        # topic="video/stream",
        base_output_folder=os.path.join(settings.MEDIA_ROOT),
        # username="admin",
        # password="letmein",
    )

    try:
        subscriber.start()
    except KeyboardInterrupt:
        subscriber.stop()
    except Exception as e:
        logger.exception(e)


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    # Start extractor in a background thread
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
