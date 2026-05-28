# Part of odoo. See LICENSE file for full copyright and licensing details.
import json
import logging

import werkzeug.wrappers

from odoo import http
from odoo.addons.weha_base_api.libs.common import invalid_response, valid_response
from odoo.http import request
from odoo.exceptions import AccessError, AccessDenied

_logger = logging.getLogger(__name__)


class AccessToken(http.Controller):
    """."""

    @http.route("/api/auth/token", methods=["GET"], type="http", auth="none", csrf=False)
    def token(self, **post):
        """The token URL to be used for getting the access_token:

        Args:
            **post must contain login and password.
        Returns:

            returns https response code 404 if failed error message in the body in json format
            and status code 202 if successful with the access_token.
        Example:
           import requests

           headers = {'content-type': 'text/plain', 'charset':'utf-8'}

           data = {
               'login': 'admin',
               'password': 'admin',
               'db': 'galago.ng'
            }
           base_url = 'http://odoo.ng'
           eq = requests.post(
               '{}/api/auth/token'.format(base_url), data=data, headers=headers)
           content = json.loads(req.content.decode('utf-8'))
           headers.update(access-token=content.get('access_token'))
        """
        _token = request.env["api.access_token"]
        params = ["db", "login", "password"]
        params = {key: post.get(key) for key in params if post.get(key)}
        db, username, password = (
            params.get("db"),
            post.get("login"),
            post.get("password"),
        )
        _credentials_includes_in_body = all([db, username, password])
        if not _credentials_includes_in_body:
            # The request post body is empty the credetials maybe passed via the headers.
            headers = request.httprequest.headers
            db = headers.get("db")
            username = headers.get("login")
            password = headers.get("password")
            _credentials_includes_in_headers = all([db, username, password])
            if not _credentials_includes_in_headers:
                # Empty 'db' or 'username' or 'password:
                return invalid_response(
                    "missing error", "either of the following are missing [db, username,password]", 403,
                )
        # Login in odoo database:
        try:
            credential = {'login': username, 'password': password, 'type': 'password'}
            request.session.authenticate(request.db, credential)
            # request.session.authenticate(db, username, password)
        except AccessError as aee:
            return invalid_response("Access error", "Error: %s" % aee.name)
        except AccessDenied as ade:
            return invalid_response("Access denied", "Login, password or db invalid")
        except Exception as e:
            # Invalid database:
            info = "The database name is not valid {}".format((e))
            error = "invalid_database"
            _logger.error(info)
            return invalid_response("wrong database name", error, 403)

        uid = request.session.uid
        # odoo login failed:
        if not uid:
            info = "authentication failed"
            error = "authentication failed"
            _logger.error(info)
            return invalid_response("authentication_failed", error, 401)

        # Generate tokens
        ip_address = request.httprequest.remote_addr
        user_agent = request.httprequest.user_agent.string
        raw_token, token_record = _token.sudo().create_token(
            user_id=uid,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        expires_in = int(
            request.env['ir.config_parameter'].sudo().get_param(
                'weha_base_api.access_token_expires_in', default='3600'
            )
        )
        # Successful response:
        return werkzeug.wrappers.Response(
            status=200,
            content_type="application/json; charset=utf-8",
            headers=[("Cache-Control", "no-store"), ("Pragma", "no-cache")],
            response=json.dumps(
                {
                    "uid": uid,
                    "company_id": request.env.user.company_id.id if uid else None,
                    "company_ids": request.env.user.company_ids.ids if uid else None,
                    "partner_id": request.env.user.partner_id.id,
                    "access_token": raw_token,
                    "expires_in": expires_in,
                }
            ),
        )

    @http.route("/api/auth/token", methods=["DELETE"], type="http", auth="none", csrf=False)
    def delete(self, **post):
        """."""
        _token = request.env["api.access_token"]
        raw_token = request.httprequest.headers.get("access_token")
        if not raw_token:
            return invalid_response("missing_token", "No access token was provided in request header", 400)
        token_record = _token.sudo().validate_token(raw_token)
        if not token_record:
            return invalid_response("invalid_token", "Access token not found or already expired", 404)
        token_record.revoke()
        # Successful response:
        return valid_response([{"desc": "access token successfully deleted", "delete": True}])
