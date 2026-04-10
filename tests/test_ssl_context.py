import os
import ssl
import unittest

import lawyer_mcp


class TestSslContext(unittest.TestCase):
    def test_insecure_ssl_env_disables_verification(self):
        os.environ["LEGALIZE_SSL_INSECURE"] = "1"
        try:
            ctx = lawyer_mcp.build_ssl_context()
            self.assertIsInstance(ctx, ssl.SSLContext)
            self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)
            self.assertFalse(ctx.check_hostname)
        finally:
            os.environ.pop("LEGALIZE_SSL_INSECURE", None)

    def test_default_ssl_context_returns_none_without_overrides(self):
        os.environ.pop("LEGALIZE_SSL_INSECURE", None)
        os.environ.pop("LEGALIZE_SSL_CERT_FILE", None)
        ctx = lawyer_mcp.build_ssl_context()
        # Either None (system default) or an SSLContext (if certifi is available).
        self.assertTrue(ctx is None or isinstance(ctx, ssl.SSLContext))
