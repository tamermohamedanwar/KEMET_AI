# Kemet AI Progress

## Support Dashboard

Completed:
- admin_support.html redesigned.
- ticket_detail.html redesigned as chat interface.
- Admin support route added:
  /admin/support
  /admin/support/ticket/<id>

Database:
- Ticket model exists.
- TicketReply model exists.
- Admin replies saved with is_staff=True.

Kemet AI:
- Connected ai_service.ask_ai().
- Added AI suggestion route:
  /admin/support/ticket/<id>/ai-suggest

Next steps:
1. Test AI suggestion button.
2. Add AI suggestion history.
3. Add approve/send workflow.
4. Improve ticket statuses.
