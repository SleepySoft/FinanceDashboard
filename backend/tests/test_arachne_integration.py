import os
import unittest
from unittest.mock import patch

from starlette.requests import Request
from starlette.responses import Response

from integrations import arachne


class ArachneIntegrationTests(unittest.TestCase):
    @staticmethod
    def _request():
        return Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    def test_auth_scope_is_read_only_without_login(self):
        response = Response()
        with patch.object(arachne.auth, "get_session_user", return_value=None):
            result = arachne.auth_scope(self._request(), response)

        self.assertEqual(result, {"scope": "read_only", "authenticated": False})
        self.assertEqual(response.headers["X-Arachne-Scope"], "read_only")

    def test_auth_scope_grants_write_to_logged_in_user(self):
        response = Response()
        with patch.object(arachne.auth, "get_session_user", return_value="sleepy"):
            result = arachne.auth_scope(self._request(), response)

        self.assertEqual(result, {"scope": "read_write", "authenticated": True})
        self.assertEqual(response.headers["X-Arachne-Scope"], "read_write")

    def test_embed_url_uses_configured_public_base(self):
        with patch.dict(os.environ, {"ARACHNE_PUBLIC_BASE": "/dashboard/arachne"}):
            url = arachne._build_embed_url("nanda_optoelectronics", "南大光电")

        self.assertTrue(url.startswith("/dashboard/arachne/embed.html?"))
        self.assertIn("seed=nanda_optoelectronics", url)
        self.assertIn("task_type=cross_graph_context", url)
        self.assertIn("title=%E5%8D%97%E5%A4%A7%E5%85%89%E7%94%B5", url)

    def test_resolve_stock_returns_unmatched_without_guessing(self):
        with patch.object(arachne, "_request_company", return_value=None):
            result = arachne.resolve_stock(" 002430.sz ")

        self.assertEqual(
            result,
            {"available": True, "matched": False, "stock_code": "002430.SZ"},
        )

    def test_resolve_stock_builds_company_embed(self):
        company = {"company_id": "nanda_optoelectronics", "name_zh": "南大光电"}
        with patch.object(arachne, "_request_company", return_value=company):
            result = arachne.resolve_stock("002430.SZ")

        self.assertTrue(result["matched"])
        self.assertEqual(result["company"], company)
        self.assertIn("seed=nanda_optoelectronics", result["embed_url"])


if __name__ == "__main__":
    unittest.main()
