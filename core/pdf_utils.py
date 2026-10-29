from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders


def pdf_link_callback(uri, _relative_uri):
    parsed = urlsplit(uri)
    resource_path = unquote(parsed.path)
    static_prefix = urlsplit(settings.STATIC_URL).path
    media_prefix = urlsplit(settings.MEDIA_URL).path

    if static_prefix and resource_path.startswith(static_prefix):
        relative_path = resource_path[len(static_prefix):].lstrip("/")
        local_path = finders.find(relative_path)
    elif media_prefix and resource_path.startswith(media_prefix):
        relative_path = resource_path[len(media_prefix):].lstrip("/")
        local_path = Path(settings.MEDIA_ROOT, relative_path)
    else:
        raise ValueError(f"Unsupported external PDF resource: {uri}")

    if not local_path or not Path(local_path).is_file():
        raise FileNotFoundError(f"PDF resource not found: {uri}")
    return str(Path(local_path).resolve())
