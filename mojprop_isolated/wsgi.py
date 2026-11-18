"""Private Passenger entry point, never a replacement for the MojPlayWin root.

The standalone ledger path is NOT a private key. Resolve its directory from
the host account instead of relying on inherited Web Server env vars. All
billing/settlement release switches remain default-OFF.
"""
import os
from pathlib import Path
import pwd

os.environ["DJANGO_SETTINGS_MODULE"] = "mojprop_isolated.settings"
account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
os.environ.setdefault(
    "MOJPROP_V141_LEDGER_PATH",
    str(account_home / ".mojprop-native-v141-isolated-20261118" / "merchant.sqlite3"),
)
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
