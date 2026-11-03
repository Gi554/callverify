"""Shared test fixture: a client with one scheduled visit and the usual auth/report helpers."""

from . import test_isolation_client as fixtures


class VisitFixture:
    setUp = fixtures.IsolationClientTests.setUp
    auth = fixtures.IsolationClientTests.auth
    report = fixtures.IsolationClientTests.report
    payload = fixtures.IsolationClientTests.payload
