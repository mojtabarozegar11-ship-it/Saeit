"""Non-mutating review of Moj Commerce MariaDB release prerequisites."""
import unittest
from unittest.mock import patch
from tools import moj_commerce_v12_live_mariadb_readonly as audit


class ReadOnlyGateTests(unittest.TestCase):
    def test_unresolved_configuration_fails_closed(self):
        with patch.object(audit, '_url_candidates', return_value=[]), \
             patch.object(audit, '_uapi_databases', return_value=set()), \
             patch.object(audit, '_quota', return_value={'quota_measured': False}):
            status = audit.inspect()
        self.assertFalse(status['config_single_unambiguous_database_url'])
        self.assertFalse(status['scoped_mysql_readonly_transaction_ok'])
        self.assertFalse(status['release_permitted'])

    def test_passenger_cannot_be_inferred_from_config(self):
        with patch.object(audit, '_url_candidates', return_value=[]), \
             patch.object(audit, '_uapi_databases', return_value=None), \
             patch.object(audit, '_quota', return_value={'quota_measured': True}):
            status = audit.inspect()
        self.assertFalse(status['actual_Passenger_db_runtime_verified'])
        self.assertFalse(status['full_database_and_media_restore_verified'])


if __name__ == '__main__':
    unittest.main()
