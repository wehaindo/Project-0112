import logging
import datetime
import json
import ast
import werkzeug.wrappers
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime, timedelta, date
import pytz

_logger = logging.getLogger(__name__)


def default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, bytes):
        return str(o)


def valid_response(data, status=200):
    """Valid Response
    This will be return when the http request was successfully processed."""
    #data = {"count": len(data) if not isinstance(data, str) else 1, "data": data}
    return werkzeug.wrappers.Response(
        status=status, 
        content_type="application/json; charset=utf-8", 
        response=json.dumps(data, default=default),
    )


def invalid_response(typ, message=None, status=401):
    """Invalid Response
    This will be the return value whenever the server runs into an error
    either from the client or the server."""
    # return json.dumps({})
    return werkzeug.wrappers.Response(
        status=status,
        content_type="application/json; charset=utf-8",
        response=json.dumps(
            {"type": typ, "message": str(message) if str(message) else "wrong arguments (missing validation)",},
            default=datetime.isoformat,
        ),
    )

def extract_arguments(payloads, offset=0, limit=0, order=None):
    """Parse additional data  sent along request."""
    payloads = payloads.get("payload", {})
    fields, domain, payload = [], [], {}

    if payloads.get("domain", None):
        domain = ast.literal_eval(payloads.get("domain"))
    if payloads.get("fields"):
        fields = ast.literal_eval(payloads.get("fields"))
    if payloads.get("offset"):
        offset = int(payloads.get("offset"))
    if payloads.get("limit"):
        limit = int(payloads.get("limit"))
    if payloads.get("order"):
        order = payloads.get("order")
    filters = [domain, fields, offset, limit, order]

    return filters

def convert_local_to_utc(user_tz, trans_date):
    _logger.info(user_tz)
    local = pytz.timezone(user_tz)
    _logger.info(trans_date)
    trans_date = local.localize(datetime.strptime(trans_date,DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(pytz.utc)
    trans_date = datetime.strftime(trans_date,"%Y-%m-%d %H:%M:%S") 
    _logger.info(trans_date)
    return trans_date

def convert_utc_to_local(user_tz, trans_date):
    _logger.info(user_tz)
    local = pytz.timezone(user_tz)
    _logger.info(trans_date)
    trans_date = pytz.utc.localize(datetime.strptime(trans_date,DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local)
    #trans_date = datetime.strftime(trans_date,"%Y-%m-%d %H:%M:%S") 
    #_logger.info(trans_date)
    return trans_date