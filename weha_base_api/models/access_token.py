import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class APIAccessToken(models.Model):
    _name = "api.access_token"
    _description = "API Access Token"
    _order = "created_at desc"

    token_hash = fields.Char("Token Hash", required=True, index=True, readonly=True)
    token_prefix = fields.Char("Token Prefix", size=8, readonly=True)
    user_id = fields.Many2one("res.users", string="User", required=True, ondelete="cascade", index=True)
    expires = fields.Datetime(string="Expires", required=True, index=True)
    scope = fields.Char(string="Scope", default="userinfo")
    last_used = fields.Datetime(string="Last Used", readonly=True)
    created_at = fields.Datetime(string="Created", default=fields.Datetime.now, readonly=True)
    ip_address = fields.Char(string="IP Address")
    user_agent = fields.Text(string="User Agent")
    device_id = fields.Char(string="Device ID", index=True)
    is_active = fields.Boolean(string="Active", default=True)

    _sql_constraints = [
        ('token_hash_unique', 'unique(token_hash)', 'Token must be unique!'),
    ]

    @api.model
    def _hash_token(self, token):
        """Hash token using SHA256 for secure storage."""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @api.model
    def _generate_token(self):
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(32)

    @api.model
    def create_token(self, user_id, scope="userinfo", ip_address=None, user_agent=None, device_id=None):
        """
        Create new access token with proper security.
        
        Returns: (raw_token, token_record)
        """
        # Generate token
        raw_token = self._generate_token()
        token_hash = self._hash_token(raw_token)
        token_prefix = raw_token[:8]
        
        # Get expiration time from config
        expires_in = int(
            self.env['ir.config_parameter'].sudo().get_param(
                'weha_base_api.access_token_expires_in',
                default='3600'  # 1 hour default
            )
        )
        expires = datetime.now() + timedelta(seconds=expires_in)
        
        vals = {
            'user_id': user_id,
            'token_hash': token_hash,
            'token_prefix': token_prefix,
            'scope': scope,
            'expires': expires,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'device_id': device_id,
        }
        
        token_record = self.sudo().create(vals)
        
        _logger.info(
            f"Token created for user {user_id} "
            f"(prefix: {token_prefix}, expires: {expires}, device: {device_id})"
        )
        
        # Return raw token (only time it's visible)
        return raw_token, token_record

    @api.model
    def validate_token(self, raw_token, required_scope=None):
        """
        Validate token and optionally check scope.
        
        Returns: token_record or False
        """
        if not raw_token:
            return False
        
        token_hash = self._hash_token(raw_token)
        
        token = self.sudo().search([
            ('token_hash', '=', token_hash),
            ('is_active', '=', True),
            ('expires', '>', fields.Datetime.now())
        ], limit=1)
        
        if not token:
            _logger.warning(f"Invalid token validation attempt (prefix: {raw_token[:8]})")
            return False
        
        # Check scope if required
        if required_scope and not token._allow_scopes([required_scope]):
            _logger.warning(
                f"Token {token.token_prefix} does not have required scope: {required_scope}"
            )
            return False
        
        # Update last used timestamp
        token.sudo().write({'last_used': fields.Datetime.now()})
        
        return token

    def is_valid(self, scopes=None):
        """Check if token is valid and has required scopes."""
        self.ensure_one()
        return (
            self.is_active and 
            not self.has_expired() and 
            self._allow_scopes(scopes)
        )

    def has_expired(self):
        """Check if token has expired."""
        self.ensure_one()
        return datetime.now() > fields.Datetime.from_string(self.expires)

    def _allow_scopes(self, scopes):
        """Check if token has all required scopes."""
        self.ensure_one()
        if not scopes:
            return True

        provided_scopes = set(self.scope.split())
        resource_scopes = set(scopes)

        return resource_scopes.issubset(provided_scopes)

    def revoke(self):
        """Revoke token (soft delete)."""
        self.ensure_one()
        self.sudo().write({'is_active': False})
        _logger.info(f"Token {self.token_prefix} revoked for user {self.user_id.id}")

    @api.model
    def _cron_cleanup_expired_tokens(self):
        """Scheduled action to clean up expired tokens."""
        # Delete tokens expired more than 30 days ago
        cutoff_date = datetime.now() - timedelta(days=30)
        
        expired_tokens = self.sudo().search([
            ('expires', '<', cutoff_date)
        ])
        
        count = len(expired_tokens)
        if count > 0:
            expired_tokens.unlink()
            _logger.info(f"Cleaned up {count} expired tokens")
        
        return True

    @api.model
    def find_or_create_token(self, user_id=None, device_id=None, create=False, **kwargs):
        """Find valid token or create new one if allowed."""
        if not user_id:
            user_id = self.env.user.id
        
        # Search for valid token
        domain = [
            ('user_id', '=', user_id),
            ('is_active', '=', True),
            ('expires', '>', fields.Datetime.now())
        ]
        
        if device_id:
            domain.append(('device_id', '=', device_id))
        
        token = self.sudo().search(domain, order='created_at DESC', limit=1)
        
        if token:
            return token.token_hash, token  # Return hash as placeholder
        
        if not create:
            return None, None
        
        # Create new token
        return self.create_token(user_id, device_id=device_id, **kwargs)


class Users(models.Model):
    _inherit = "res.users"
    
    token_ids = fields.One2many("api.access_token", "user_id", string="Access Tokens")
    active_token_count = fields.Integer(
        string="Active Tokens", 
        compute="_compute_active_token_count"
    )

    @api.depends('token_ids')
    def _compute_active_token_count(self):
        """Compute number of active, non-expired tokens."""
        for user in self:
            user.active_token_count = self.env['api.access_token'].sudo().search_count([
                ('user_id', '=', user.id),
                ('is_active', '=', True),
                ('expires', '>', fields.Datetime.now())
            ])

    def write(self, vals):
        """Revoke all tokens when password or login changes."""
        result = super(Users, self).write(vals)
        
        if 'password' in vals or 'login' in vals:
            for user in self:
                active_tokens = user.token_ids.filtered(
                    lambda t: t.is_active and not t.has_expired()
                )
                if active_tokens:
                    active_tokens.revoke()
                    _logger.info(
                        f"Revoked {len(active_tokens)} tokens for user {user.id} "
                        f"due to {'password' if 'password' in vals else 'login'} change"
                    )
        
        return result

    def action_revoke_all_tokens(self):
        """Action to revoke all user tokens."""
        self.ensure_one()
        active_tokens = self.token_ids.filtered(lambda t: t.is_active)
        active_tokens.revoke()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'{len(active_tokens)} token(s) revoked successfully',
                'type': 'success',
                'sticky': False,
            }
        }