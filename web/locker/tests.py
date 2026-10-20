"""Django web-client tests.

All HTTP calls to FastAPI are mocked at `locker.fastapi_client.requests`;
no live backend, no Supabase, no network access.
"""
import requests as real_requests
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import fastapi_client
from .views import DETAIL_QUOTA, DETAIL_TOO_LARGE

JWT = "jwt-test-token-do-not-leak"


def make_response(status=200, json_data=None, headers=None, content=b""):
    class _Resp:
        pass

    r = _Resp()
    r.status_code = status
    r.json_data = json_data if json_data is not None else {}
    r.json = lambda: r.json_data
    r.headers = headers or {}
    r.content = content
    r.iter_content = lambda chunk_size: iter([content])
    r.close = lambda: None
    return r


DOC = {
    "id": "11111111-2222-3333-4444-555555555555",
    "filename": "notes.pdf",
    "file_type": "application/pdf",
    "file_size_bytes": 1234,
    "created_at": "2026-10-20T10:00:00Z",
    "updated_at": "2026-10-20T10:00:00Z",
}

USAGE = {"used_bytes": 1234, "quota_bytes": 524288000, "document_count": 1}


class MockedAPITestCase(TestCase):
    """Base: patches locker.fastapi_client.requests with a route table."""

    def setUp(self):
        patcher = patch("locker.fastapi_client.requests")
        self.requests = patcher.start()
        # Keep exception classes real so `except requests.RequestException`
        # in fastapi_client works while the module is mocked.
        self.requests.RequestException = real_requests.RequestException
        self.addCleanup(patcher.stop)
        self.routes = {}
        self.calls = []
        self.requests.request.side_effect = self._route
        self.requests.get.side_effect = self._route

    def _route(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        for (m, suffix), resp in self.routes.items():
            if method == m and url.endswith(suffix):
                return resp
        raise AssertionError(f"unexpected API call: {method} {url}")

    def route(self, method, suffix, status=200, json_data=None, **kwargs):
        self.routes[(method.upper(), suffix)] = make_response(
            status, json_data, **kwargs
        )

    def _login(self):
        self.route("POST", "/auth/login", json_data={
            "access_token": JWT, "token_type": "bearer", "expires_in": 86400,
        })
        resp = self.client.post(
            reverse("locker:login"),
            {"email": "ana@example.com", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 302)
        return resp

    def _seed_session(self):
        """Simulate an already-authenticated session."""
        self._login()

    def _api_doc_calls(self):
        self.route("GET", "/documents/usage", json_data=USAGE)
        self.route("GET", "/documents", json_data=[DOC])


class AuthFlowTests(MockedAPITestCase):
    def test_register_auto_login_rotates_session_and_stores_jwt(self):
        s = self.client.session
        s["probe"] = "1"
        s.save()
        key_before = self.client.session.session_key
        self.route("POST", "/auth/register", status=201, json_data={"id": "u", "email": "a@b.c"})
        self.route("POST", "/auth/login", json_data={
            "access_token": JWT, "token_type": "bearer", "expires_in": 86400,
        })
        resp = self.client.post(
            reverse("locker:register"),
            {"email": "a@b.co", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/")
        self.assertNotEqual(self.client.session.session_key, key_before)
        self.assertEqual(self.client.session["api_token"], JWT)
        # register call normalized the email
        method, url, kw = self.calls[0]
        self.assertEqual((method, url.endswith("/auth/register")), ("POST", True))
        self.assertEqual(kw["json"]["email"], "a@b.co")

    def test_register_duplicate_email_shows_error(self):
        self.route("POST", "/auth/register", status=409,
                   json_data={"detail": "Email already registered"})
        resp = self.client.post(
            reverse("locker:register"),
            {"email": "a@b.co", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already exists")
        self.assertNotIn("api_token", self.client.session)

    def test_login_rotates_session_key(self):
        s = self.client.session
        s["probe"] = "1"
        s.save()
        key_before = self.client.session.session_key
        self._login()
        self.assertNotEqual(self.client.session.session_key, key_before)
        self.assertEqual(self.client.session["api_token"], JWT)

    def test_login_wrong_password_generic_error(self):
        self.route("POST", "/auth/login", status=401,
                   json_data={"detail": "Incorrect email or password"})
        resp = self.client.post(
            reverse("locker:login"),
            {"email": "a@b.co", "password": "wrongpass1"},
        )
        self.assertEqual(resp.status_code, 302)
        page = self.client.get(resp.url)
        self.assertContains(page, "Incorrect email or password")
        self.assertNotIn("api_token", self.client.session)

    def test_logout_is_post_only_and_clears_session(self):
        self._login()
        get_resp = self.client.get(reverse("locker:logout"))
        self.assertEqual(get_resp.status_code, 405)
        resp = self.client.post(reverse("locker:logout"))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("api_token", self.client.session)

    def test_unauthenticated_pages_redirect_to_login(self):
        for name in ("dashboard", "upload"):
            url = reverse(f"locker:{name}")
            resp = self.client.post(url, {}) if name == "upload" else self.client.get(url)
            self.assertEqual(resp.status_code, 302, name)
            self.assertTrue(resp.url.startswith("/login"), resp.url)

    def test_jwt_never_appears_in_html_or_urls_or_cookies(self):
        self._seed_session()
        self._api_doc_calls()
        resp = self.client.get(reverse("locker:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(JWT, resp.content.decode())
        # The session cookie holds only the opaque session key, never the JWT.
        session_cookie = self.client.cookies.get("sessionid")
        if session_cookie is not None:
            self.assertNotIn(JWT, session_cookie.value)
        # None of the backend calls put the token in a URL.
        for _m, url, _kw in self.calls:
            self.assertNotIn(JWT, url)


class CsrfTests(MockedAPITestCase):
    def test_state_changing_routes_require_csrf(self):
        c = Client(enforce_csrf_checks=True)
        cases = [
            ("login", {}),
            ("register", {}),
            ("logout", {}),
            ("upload", {}),
        ]
        for name, data in cases:
            resp = c.post(reverse(f"locker:{name}"), data)
            self.assertEqual(resp.status_code, 403, name)
        doc_id = "11111111-2222-3333-4444-555555555555"
        for name in ("rename", "delete"):
            resp = c.post(
                reverse(f"locker:{name}", kwargs={"document_id": doc_id}),
                {"filename": "x.txt"},
            )
            self.assertEqual(resp.status_code, 403, name)

    def test_csrf_token_emitted_by_form_allows_post(self):
        """A real token extracted from the rendered page must pass the middleware."""
        c = Client(enforce_csrf_checks=True)
        page = c.get(reverse("locker:login"))
        self.assertEqual(page.status_code, 200)
        token = c.cookies["csrftoken"].value
        self.assertIn("csrfmiddlewaretoken", page.content.decode())
        self.route("POST", "/auth/login", status=401,
                   json_data={"detail": "Incorrect email or password"})
        resp = c.post(
            reverse("locker:login"),
            {"email": "a@b.co", "password": "wrongpass1",
             "csrfmiddlewaretoken": token},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(resp.status_code, 403)


class DashboardTests(MockedAPITestCase):
    def test_dashboard_lists_documents_and_usage(self):
        self._seed_session()
        self._api_doc_calls()
        resp = self.client.get(reverse("locker:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "notes.pdf")
        self.assertContains(resp, "usage-bar")

    def test_search_sort_filter_params_forwarded(self):
        self._seed_session()
        self._api_doc_calls()
        self.client.get(
            "/?search=notes&sort=filename&order=asc&file_type=application/pdf"
        )
        doc_calls = [kw for m, u, kw in self.calls if m == "GET" and u.endswith("/documents")]
        self.assertEqual(len(doc_calls), 1)
        self.assertEqual(
            doc_calls[0]["params"],
            {"search": "notes", "sort": "filename", "order": "asc",
             "file_type": "application/pdf"},
        )

    def test_dashboard_network_failure_shows_generic_message(self):
        self._seed_session()
        self.requests.request.side_effect = real_requests.ConnectionError
        resp = self.client.get(reverse("locker:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Cannot reach the service")

    def test_expired_401_flushes_session_and_redirects_to_login(self):
        self._seed_session()
        self.route("GET", "/documents/usage", status=401,
                   json_data={"detail": "missing credentials"})
        resp = self.client.get(reverse("locker:dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/login/")
        self.assertNotIn("api_token", self.client.session)
        follow = self.client.get(resp.url)
        self.assertContains(follow, "session has expired")

    def test_invalid_sort_422_handled(self):
        self._seed_session()
        self.route("GET", "/documents/usage", json_data=USAGE)
        self.route("GET", "/documents", status=422, json_data={"detail": "bad"})
        resp = self.client.get(reverse("locker:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid search or sort options")


class UploadTests(MockedAPITestCase):
    def _upload(self, name="f.pdf", content=b"%PDF", size=None):
        if size is not None:
            content = b"x" * size
        return self.client.post(
            reverse("locker:upload"),
            {"file": SimpleUploadedFile(name, content, content_type="application/pdf")},
        )

    def test_upload_success(self):
        self._seed_session()
        self._api_doc_calls()
        self.route("POST", "/documents", status=201, json_data=DOC)
        resp = self._upload()
        self.assertEqual(resp.status_code, 302)
        upload_calls = [kw for m, u, kw in self.calls if m == "POST" and u.endswith("/documents")]
        self.assertEqual(len(upload_calls), 1)
        self.assertIn("files", upload_calls[0])
        follow = self.client.get(resp.url)
        self.assertContains(follow, "Uploaded")

    @override_settings(MAX_UPLOAD_BYTES=10)
    def test_upload_precheck_rejects_oversize_locally(self):
        self._seed_session()
        self._api_doc_calls()
        resp = self._upload(content=b"y" * 50)
        self.assertEqual(resp.status_code, 302)
        follow = self.client.get(resp.url)
        self.assertContains(follow, "50 MiB")
        self.assertFalse([c for c in self.calls if c[1].endswith("/documents") and c[0] == "POST"])

    def test_upload_413_quota_vs_size_use_distinct_messages(self):
        self._seed_session()
        self._api_doc_calls()
        self.route("POST", "/documents", status=413, json_data={"detail": DETAIL_QUOTA})
        resp = self._upload()
        self.assertContains(self.client.get(resp.url), "Storage quota reached")

        self.route("POST", "/documents", status=413,
                   json_data={"detail": DETAIL_TOO_LARGE})
        resp = self._upload()
        self.assertContains(self.client.get(resp.url), "larger than the 50 MiB limit")

    def test_upload_network_failure_generic_message(self):
        self._seed_session()
        self._api_doc_calls()

        def side_effect(m, u, **kw):
            if m == "POST" and u.endswith("/documents"):
                raise real_requests.ConnectionError()
            if u.endswith("/documents/usage"):
                return make_response(200, USAGE)
            if u.endswith("/documents"):
                return make_response(200, [DOC])
            raise AssertionError(f"unexpected: {m} {u}")

        self.requests.request.side_effect = side_effect
        resp = self._upload()
        follow = self.client.get(resp.url)
        self.assertContains(follow, "Cannot reach the service")


class DocumentActionTests(MockedAPITestCase):
    DOC_ID = "11111111-2222-3333-4444-555555555555"

    def test_download_preserves_content_type_and_disposition(self):
        self._seed_session()
        self.route("GET", f"/documents/{self.DOC_ID}", content=b"%PDF-bytes", headers={
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="notes.pdf"',
        })
        resp = self.client.get(
            reverse("locker:download", kwargs={"document_id": self.DOC_ID})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertEqual(resp["Content-Disposition"], 'attachment; filename="notes.pdf"')
        self.assertEqual(b"".join(resp.streaming_content), b"%PDF-bytes")

    def test_download_404_shows_safe_message(self):
        self._seed_session()
        self._api_doc_calls()
        self.route("GET", f"/documents/{self.DOC_ID}", status=404,
                   json_data={"detail": "Document not found"})
        resp = self.client.get(
            reverse("locker:download", kwargs={"document_id": self.DOC_ID})
        )
        self.assertEqual(resp.status_code, 302)
        follow = self.client.get(resp.url)
        self.assertContains(follow, "Document not found")

    def test_rename_get_form_and_post_success(self):
        self._seed_session()
        resp = self.client.get(
            reverse("locker:rename", kwargs={"document_id": self.DOC_ID})
        )
        self.assertEqual(resp.status_code, 200)
        self.route("PATCH", f"/documents/{self.DOC_ID}", json_data={**DOC, "filename": "new.pdf"})
        resp = self.client.post(
            reverse("locker:rename", kwargs={"document_id": self.DOC_ID}),
            {"filename": "new.pdf"},
        )
        self.assertEqual(resp.status_code, 302)
        patch_calls = [kw for m, u, kw in self.calls if m == "PATCH"]
        self.assertEqual(patch_calls[0]["json"], {"filename": "new.pdf"})

    def test_rename_invalid_name_rejected_locally_without_api_call(self):
        self._seed_session()
        resp = self.client.post(
            reverse("locker:rename", kwargs={"document_id": self.DOC_ID}),
            {"filename": "../evil.txt"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "path separators")
        self.assertFalse([c for c in self.calls if c[0] == "PATCH"])

    def test_rename_404_safe_message(self):
        self._seed_session()
        self._api_doc_calls()
        self.route("PATCH", f"/documents/{self.DOC_ID}", status=404,
                   json_data={"detail": "Document not found"})
        resp = self.client.post(
            reverse("locker:rename", kwargs={"document_id": self.DOC_ID}),
            {"filename": "ok.pdf"},
        )
        follow = self.client.get(resp.url)
        self.assertContains(follow, "Document not found")

    def test_delete_requires_confirmation_page_then_post(self):
        self._seed_session()
        self._api_doc_calls()
        url = reverse("locker:delete", kwargs={"document_id": self.DOC_ID})
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, "cannot be undone")
        self.assertFalse([c for c in self.calls if c[0] == "DELETE"])

        self.route("DELETE", f"/documents/{self.DOC_ID}", status=204)
        post_resp = self.client.post(url)
        self.assertEqual(post_resp.status_code, 302)
        self.assertTrue([c for c in self.calls if c[0] == "DELETE"])
        follow = self.client.get(post_resp.url)
        self.assertContains(follow, "Document deleted")

    def test_unauthenticated_document_actions_redirect_to_login(self):
        doc_id = self.DOC_ID
        checks = [
            self.client.get(reverse("locker:download", kwargs={"document_id": doc_id})),
            self.client.post(reverse("locker:rename", kwargs={"document_id": doc_id}), {"filename": "a.txt"}),
            self.client.post(reverse("locker:delete", kwargs={"document_id": doc_id})),
        ]
        for resp in checks:
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp.url.startswith("/login"), resp.url)


class ErrorDetailTests(TestCase):
    def test_detail_parsing_handles_list_payload(self):
        """FastAPI 422 returns detail as a list; the client must not crash."""

        class R:
            status_code = 422

            @staticmethod
            def json():
                return {"detail": [{"msg": "bad"}]}

        self.assertEqual(fastapi_client._detail(R()), "[{'msg': 'bad'}]")


AI_STATUS = {
    "configured": True,
    "provider": "openrouter",
    "model": "minimax/minimax-m3.1-flash:free",
    "local_ai": "unavailable",
}

ASK_RESULT = {
    "answer": "Your registration number is 12345.",
    "sources": [
        {"document_id": DOC["id"], "filename": "internship_certificate.txt"}
    ],
    "model": "minimax/minimax-m3.1-flash:free",
    "relevant_documents_found": True,
}

NO_MATCH_RESULT = {
    "answer": "I couldn't find any documents that look relevant to that question.",
    "sources": [],
    "model": "minimax/minimax-m3.1-flash:free",
    "relevant_documents_found": False,
}

SUMMARIZE_RESULT = {
    "summary": "Q3 revenue rose 12%.",
    "sources": [{"document_id": DOC["id"], "filename": "report.txt"}],
    "model": "minimax/minimax-m3.1-flash:free",
}

SUGGEST_RESULT = {
    "current_filename": "file1.txt",
    "suggested_filename": "internship_certificate_2026.txt",
    "reason": "Proposal only - renaming requires your confirmation.",
    "model": "minimax/minimax-m3.1-flash:free",
}


class AITests(MockedAPITestCase):
    def _seed_ai(self):
        self._seed_session()
        self.route("GET", "/ai/status", json_data=AI_STATUS)
        self._api_doc_calls()

    def test_ai_page_requires_login(self):
        resp = self.client.get(reverse("locker:ai"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith("/login"), resp.url)

    def test_ai_page_shows_status_and_local_placeholder(self):
        self._seed_ai()
        resp = self.client.get(reverse("locker:ai"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "minimax/minimax-m3.1-flash:free")
        self.assertContains(resp, "Local AI")
        self.assertContains(resp, "unavailable")

    def test_ask_returns_answer_with_sources(self):
        self._seed_ai()
        self.route("POST", "/ai/ask", json_data=ASK_RESULT)
        resp = self.client.post(reverse("locker:ai"), {"action": "ask", "question": "What is my registration number?"})
        self.assertContains(resp, "Your registration number is 12345.")
        self.assertContains(resp, "internship_certificate.txt")
        method, url, kw = self.calls[-1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/ai/ask"))
        self.assertEqual(kw["json"], {"question": "What is my registration number?"})

    def test_ask_with_no_relevant_documents_shows_honest_answer(self):
        self._seed_ai()
        self.route("POST", "/ai/ask", json_data=NO_MATCH_RESULT)
        resp = self.client.post(reverse("locker:ai"), {"action": "ask", "question": "quantum rockets"})
        self.assertContains(resp, "couldn&#x27;t find any documents")

    def test_summarize_shows_summary(self):
        self._seed_ai()
        self.route("POST", "/ai/summarize", json_data=SUMMARIZE_RESULT)
        resp = self.client.post(
            reverse("locker:ai"),
            {"action": "summarize", "document_id": DOC["id"]},
        )
        self.assertContains(resp, "Q3 revenue rose 12%.")

    def test_suggest_is_proposal_with_confirm_link_to_existing_rename(self):
        self._seed_ai()
        self.route("POST", "/ai/suggest-filename", json_data=SUGGEST_RESULT)
        resp = self.client.post(
            reverse("locker:ai"),
            {"action": "suggest", "document_id": DOC["id"]},
        )
        self.assertContains(resp, "internship_certificate_2026.txt")
        rename_url = reverse("locker:rename", kwargs={"document_id": DOC["id"]})
        self.assertContains(resp, rename_url)

    def test_provider_503_shows_safe_message(self):
        self._seed_ai()
        self.route(
            "POST", "/ai/ask", status=503,
            json_data={"detail": "The AI provider is busy. Please try again shortly."},
        )
        resp = self.client.post(reverse("locker:ai"), {"action": "ask", "question": "hi"})
        self.assertContains(resp, "busy")

    def test_unsupported_format_shows_422_detail(self):
        self._seed_ai()
        self.route(
            "POST", "/ai/summarize", status=422,
            json_data={"detail": "Text extraction is not supported for this format yet."},
        )
        resp = self.client.post(
            reverse("locker:ai"),
            {"action": "summarize", "document_id": DOC["id"]},
        )
        self.assertContains(resp, "not supported")

    def test_session_expired_on_ai_redirects_to_login(self):
        self._seed_session()
        self.route("GET", "/ai/status", status=401, json_data={"detail": "Invalid token"})
        resp = self.client.get(reverse("locker:ai"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith("/login"), resp.url)

    def test_floating_ai_button_visible_only_when_logged_in(self):
        self._seed_ai()
        logged_in = self.client.get(reverse("locker:dashboard"))
        self.assertContains(logged_in, 'class="floating-ai"')
        self.client.post(reverse("locker:logout"))
        logged_out = self.client.get(reverse("locker:login"))
        self.assertNotContains(logged_out, 'class="floating-ai"')
