#!/usr/bin/env python
import os
import sys
def main():
    debug = os.getenv('DEBUG', '0') == '1'
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'config.settings.dev' if debug else 'config.settings.prod',
    )
    from core.sentry import init_sentry
    init_sentry(service_name="django-manage", enable_django=True)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
if __name__ == '__main__':
    main()
