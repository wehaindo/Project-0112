import json
import logging
import functools

import odoo
import odoo.modules.registry
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.service import security
from odoo.tools import ustr
from odoo.tools.translate import _
from odoo.addons.weha_base_api.libs.common import (
    extract_arguments,
    invalid_response,
    valid_response,
)


_logger = logging.getLogger(__name__)

def validate_token(func):
    """Decorator to validate API access token on protected routes."""

    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        """."""
        access_token = request.httprequest.headers.get("access_token")
        if not access_token:
            return invalid_response("access_token_not_found", "missing access token in request header", 401)

        access_token_data = request.env["api.access_token"].sudo().validate_token(access_token)
        if not access_token_data:
            return invalid_response("access_token", "token seems to have expired or invalid", 401)

        request.session.uid = access_token_data.user_id.id
        request.update_env(user=request.session.uid)
        return func(self, *args, **kwargs)

    return wrap

class BaseAPI(http.Controller):    
    
    @validate_token
    @http.route('/testauth', type="http", auth="none", methods=["POST"], csrf=False)
    def testauth(self, **post):               
        data = {
            "err": False,
            "message": "Test Auth Success",
            "data": []
        }
        return valid_response(data)
