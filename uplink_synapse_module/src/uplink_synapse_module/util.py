import html
import json
import logging
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Request
from synapse.module_api import run_in_background
from typing import Any

logger = logging.getLogger(__name__)

def kerb_exists(kerb):
    return True # TODO: revert this behavior!
    try:
        answers = dns.resolver.resolve(f'{kerb}.pobox.ns.athena.mit.edu', 'TXT')
        return True
    except dns.resolver.NXDOMAIN:
        return False
    
def get_username(mxid: str) -> str:
    localpart, homeserver = mxid[1:].split(':', maxsplit=1)
    return localpart

# general purpose functions stolen from
# https://github.com/matrix-org/matrix-synapse-saml-mozilla/blob/main/matrix_synapse_saml_mozilla/username_picker.py

HTML_ERROR_TEMPLATE = """<!DOCTYPE html>
<html lang=en>
  <head>
    <meta charset="utf-8">
    <title>Error {code}</title>
  </head>
  <body>
     <p>{msg}</p>
  </body>
</html>
"""


def _wrap_for_html_exceptions(f):
    async def wrapped(self, request):
        try:
            return await f(self, request)
        except Exception:
            logger.exception("Error handling request %s" % (request,))
            _return_html_error(500, "Internal server error", request)

    return wrapped


def _wrap_for_text_exceptions(f):
    async def wrapped(self, request):
        try:
            return await f(self, request)
        except Exception:
            logger.exception("Error handling request %s" % (request,))
            body = b"Internal server error"
            request.setResponseCode(500)
            request.setHeader(b"Content-Type", b"text/plain; charset=utf-8")
            request.setHeader(b"Content-Length", b"%i" % (len(body),))
            request.write(body)
            request.finish()

    return wrapped


class AsyncResource(Resource):
    """Extends twisted.web.Resource to add support for async_render_X methods"""

    def render(self, request: Request):
        method = request.method.decode("ascii")
        m = getattr(self, "async_render_" + method, None)
        if not m and method == "HEAD":
            m = getattr(self, "async_render_GET", None)
        if not m:
            return super().render(request)

        async def run():
            with request.processing():
                return await m(request)

        run_in_background(run)
        return NOT_DONE_YET


def _return_html_error(code: int, msg: str, request: Request):
    """Sends an HTML error page"""
    body = HTML_ERROR_TEMPLATE.format(code=code, msg=html.escape(msg)).encode("utf-8")
    request.setResponseCode(code)
    request.setHeader(b"Content-Type", b"text/html; charset=utf-8")
    request.setHeader(b"Content-Length", b"%i" % (len(body),))
    request.write(body)
    try:
        request.finish()
    except RuntimeError as e:
        logger.info("Connection disconnected before response was written: %r", e)


def _return_json(json_obj: Any, request: Request):
    json_bytes = json.dumps(json_obj).encode("utf-8")

    request.setHeader(b"Content-Type", b"application/json")
    request.setHeader(b"Content-Length", b"%d" % (len(json_bytes),))
    request.setHeader(b"Cache-Control", b"no-cache, no-store, must-revalidate")
    request.setHeader(b"Access-Control-Allow-Origin", b"*")
    request.setHeader(
        b"Access-Control-Allow-Methods", b"GET, POST, PUT, DELETE, OPTIONS"
    )
    request.setHeader(
        b"Access-Control-Allow-Headers",
        b"Origin, X-Requested-With, Content-Type, Accept, Authorization",
    )
    request.write(json_bytes)
    try:
        request.finish()
    except RuntimeError as e:
        logger.info("Connection disconnected before response was written: %r", e)