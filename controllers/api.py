# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(data, status=200):
    """Helper to return JSON response."""
    return Response(
        json.dumps(data, default=str),
        content_type='application/json',
        status=status
    )


class HelpdeskAPI(http.Controller):
    """REST API controller for Helpdesk Web Dashboard.
    
    All endpoints use type='json' which means:
    - Request body must be JSON-RPC format: {jsonrpc:'2.0', method:'call', params:{...}}
    - The 'params' dict is passed as **kwargs to the controller method
    - Return value is automatically wrapped in JSON-RPC response
    """

    # ─── AUTH & USER INFO ────────────────────────────────────────────

    @http.route('/api/helpdesk/auth/login', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_login(self, email='', name='', **kwargs):
        """Authenticate user by email (from Google SSO). Returns user info and role."""
        email = email.strip().lower()
        
        if not email:
            return {'success': False, 'error': 'Email is required'}
        
        # Find or create partner by email
        Partner = request.env['res.partner'].sudo()
        User = request.env['res.users'].sudo()
        
        user = User.search([('login', '=', email)], limit=1)
        
        if not user:
            # Check if partner exists
            partner = Partner.search([('email', '=', email)], limit=1)
            if not partner:
                # Create partner for new employee
                partner = Partner.create({
                    'name': name or email.split('@')[0],
                    'email': email,
                })
            
            # Determine role - default is staff
            role = 'employee'
        else:
            partner = user.partner_id
            # Check if user is helpdesk manager
            manager_group = request.env.ref('kodingyuk_helpdesk.group_helpdesk_manager', raise_if_not_found=False)
            if manager_group and manager_group.id in user.groups_id.ids:
                role = 'admin'
            else:
                role = 'employee'
        
        return {
            'success': True,
            'user': {
                'id': partner.id,
                'name': partner.name,
                'email': email,
                'role': role,
            }
        }

    # ─── MASTER DATA ─────────────────────────────────────────────────

    @http.route('/api/helpdesk/master/systems', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_get_systems(self, **kwargs):
        """Get list of active system types."""
        systems = request.env['helpdesk.system.type'].sudo().search_read(
            [('active', '=', True)],
            ['id', 'name'],
            order='name'
        )
        return {'success': True, 'data': systems}

    @http.route('/api/helpdesk/master/issue-types', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_get_issue_types(self, **kwargs):
        """Get list of active issue types."""
        issue_types = request.env['helpdesk.issue.type'].sudo().search_read(
            [('active', '=', True)],
            ['id', 'name'],
            order='name'
        )
        return {'success': True, 'data': issue_types}

    # ─── TICKETS ─────────────────────────────────────────────────────

    @http.route('/api/helpdesk/tickets', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_get_tickets(self, partner_id=None, state=None, system_id=None, 
                        issue_type_id=None, search='', offset=0, limit=20,
                        order='date desc, id desc', **kwargs):
        """Get tickets with optional filters."""
        domain = []
        
        if partner_id:
            domain.append(('staff_id', '=', int(partner_id)))
        
        if state:
            if isinstance(state, list):
                domain.append(('state', 'in', state))
            else:
                domain.append(('state', '=', state))
        
        if system_id:
            domain.append(('system_id', '=', int(system_id)))
        
        if issue_type_id:
            domain.append(('issue_type_id', '=', int(issue_type_id)))
        
        search = (search or '').strip()
        if search:
            domain += ['|', '|',
                ('name', 'ilike', search),
                ('chronology', 'ilike', search),
                ('staff_id.name', 'ilike', search),
            ]
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        
        total = Ticket.search_count(domain)
        tickets = Ticket.search_read(
            domain,
            ['id', 'name', 'staff_id', 'system_id', 'issue_type_id',
             'chronology', 'data_to_fix', 'date', 'state'],
            offset=int(offset),
            limit=int(limit),
            order=order
        )
        
        # Format many2one fields as {id, name}
        for t in tickets:
            t['staff_id'] = {'id': t['staff_id'][0], 'name': t['staff_id'][1]} if t['staff_id'] else None
            t['system_id'] = {'id': t['system_id'][0], 'name': t['system_id'][1]} if t['system_id'] else None
            t['issue_type_id'] = {'id': t['issue_type_id'][0], 'name': t['issue_type_id'][1]} if t['issue_type_id'] else None
        
        return {
            'success': True,
            'data': tickets,
            'total': total,
            'offset': offset,
            'limit': limit,
        }

    @http.route('/api/helpdesk/tickets/detail', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_get_ticket_detail(self, ticket_id=None, **kwargs):
        """Get single ticket detail with attachments and messages."""
        if not ticket_id:
            return {'success': False, 'error': 'ticket_id is required'}
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        ticket = Ticket.browse(int(ticket_id))
        
        if not ticket.exists():
            return {'success': False, 'error': 'Ticket not found'}
        
        attachments = []
        for att in ticket.attachment_ids:
            attachments.append({
                'id': att.id,
                'name': att.name,
                'url': att.url,
                'mimetype': att.mimetype,
                'file_path': att.file_path,
            })
        
        # Get message log (mail.message)
        messages = []
        for msg in ticket.message_ids:
            if msg.message_type in ('comment', 'notification'):
                messages.append({
                    'id': msg.id,
                    'date': msg.date,
                    'author': msg.author_id.name if msg.author_id else 'System',
                    'body': msg.body,
                    'message_type': msg.message_type,
                    'subtype': msg.subtype_id.name if msg.subtype_id else None,
                })
        
        return {
            'success': True,
            'data': {
                'id': ticket.id,
                'name': ticket.name,
                'staff_id': {'id': ticket.staff_id.id, 'name': ticket.staff_id.name} if ticket.staff_id else None,
                'system_id': {'id': ticket.system_id.id, 'name': ticket.system_id.name} if ticket.system_id else None,
                'issue_type_id': {'id': ticket.issue_type_id.id, 'name': ticket.issue_type_id.name} if ticket.issue_type_id else None,
                'chronology': ticket.chronology,
                'data_to_fix': ticket.data_to_fix,
                'date': ticket.date,
                'state': ticket.state,
                'attachments': attachments,
                'messages': messages,
            }
        }

    @http.route('/api/helpdesk/tickets/create', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_create_ticket(self, staff_id=None, system_id=None, issue_type_id=None,
                          chronology='', data_to_fix='', attachments=None, **kwargs):
        """Create a new ticket."""
        if not staff_id or not system_id or not issue_type_id or not chronology or not data_to_fix:
            return {'success': False, 'error': 'staff_id, system_id, issue_type_id, chronology, and data_to_fix are required'}
        
        vals = {
            'staff_id': int(staff_id),
            'system_id': int(system_id),
            'issue_type_id': int(issue_type_id),
            'chronology': chronology,
            'data_to_fix': data_to_fix,
        }
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        ticket = Ticket.create(vals)
        
        # If attachments provided (list of {name, file_path, url, mimetype})
        if attachments:
            for att in attachments:
                request.env['helpdesk.firebase.attachment'].sudo().create({
                    'name': att.get('name', 'file'),
                    'file_path': att.get('file_path', ''),
                    'url': att.get('url', ''),
                    'mimetype': att.get('mimetype', ''),
                    'ticket_id': ticket.id,
                })
        
        return {
            'success': True,
            'data': {
                'id': ticket.id,
                'name': ticket.name,
            }
        }

    @http.route('/api/helpdesk/tickets/update-state', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_update_ticket_state(self, ticket_id=None, state=None, **kwargs):
        """Update ticket state (admin action)."""
        if not ticket_id or not state:
            return {'success': False, 'error': 'ticket_id and state are required'}
        
        valid_states = ['new', 'in_progress', 'solved', 'cancelled']
        if state not in valid_states:
            return {'success': False, 'error': f'Invalid state. Must be one of: {valid_states}'}
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        ticket = Ticket.browse(int(ticket_id))
        
        if not ticket.exists():
            return {'success': False, 'error': 'Ticket not found'}
        
        ticket.write({'state': state})
        
        return {'success': True, 'data': {'id': ticket.id, 'state': ticket.state}}

    @http.route('/api/helpdesk/tickets/add-note', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_add_note(self, ticket_id=None, body='', message_type='comment', **kwargs):
        """Add internal note or message to ticket."""
        if not ticket_id or not body:
            return {'success': False, 'error': 'ticket_id and body are required'}
        
        body = body.strip()
        if not body:
            return {'success': False, 'error': 'body cannot be empty'}
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        ticket = Ticket.browse(int(ticket_id))
        
        if not ticket.exists():
            return {'success': False, 'error': 'Ticket not found'}
        
        subtype = 'mail.mt_note' if message_type == 'note' else 'mail.mt_comment'
        ticket.message_post(body=body, subtype_xmlid=subtype)
        
        return {'success': True}

    @http.route('/api/helpdesk/tickets/add-attachment', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_add_attachment(self, ticket_id=None, attachments=None, **kwargs):
        """Add Firebase attachment to existing ticket."""
        if not ticket_id or not attachments:
            return {'success': False, 'error': 'ticket_id and attachments are required'}
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        ticket = Ticket.browse(int(ticket_id))
        
        if not ticket.exists():
            return {'success': False, 'error': 'Ticket not found'}
        
        # Check max 5 attachments
        current_count = len(ticket.attachment_ids)
        if current_count + len(attachments) > 5:
            return {'success': False, 'error': f'Maximum 5 attachments allowed. Currently has {current_count}.'}
        
        created = []
        for att in attachments:
            rec = request.env['helpdesk.firebase.attachment'].sudo().create({
                'name': att.get('name', 'file'),
                'file_path': att.get('file_path', ''),
                'url': att.get('url', ''),
                'mimetype': att.get('mimetype', ''),
                'ticket_id': ticket.id,
            })
            created.append({'id': rec.id, 'name': rec.name, 'url': rec.url})
        
        return {'success': True, 'data': created}

    # ─── STATISTICS (Admin) ──────────────────────────────────────────

    @http.route('/api/helpdesk/stats', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def api_get_stats(self, **kwargs):
        """Get ticket statistics for admin dashboard."""
        import datetime
        
        Ticket = request.env['kodingyuk.helpdesk.ticket'].sudo()
        
        today = fields.Date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        stats = {
            'total': Ticket.search_count([]),
            'new': Ticket.search_count([('state', '=', 'new')]),
            'in_progress': Ticket.search_count([('state', '=', 'in_progress')]),
            'solved': Ticket.search_count([('state', '=', 'solved')]),
            'cancelled': Ticket.search_count([('state', '=', 'cancelled')]),
            'today': Ticket.search_count([('date', '>=', fields.Datetime.to_string(today))]),
            'this_week': Ticket.search_count([('date', '>=', fields.Datetime.to_string(week_start))]),
            'this_month': Ticket.search_count([('date', '>=', fields.Datetime.to_string(month_start))]),
        }
        
        # Stats per issue type
        issue_types = request.env['helpdesk.issue.type'].sudo().search([('active', '=', True)])
        by_issue_type = []
        for it in issue_types:
            count = Ticket.search_count([('issue_type_id', '=', it.id)])
            by_issue_type.append({'id': it.id, 'name': it.name, 'count': count})
        
        stats['by_issue_type'] = by_issue_type
        
        return {'success': True, 'data': stats}
