# engines/research_agent/channels/whatsapp/__init__.py
# WhatsApp channel — Meta WhatsApp Cloud API (test number, free tier).
#
# Scope, IN/OUT decisions and the phase plan: FEATURE_WHATSAPP.md
# Hard rules: CLAUDE.md → "Hard Rules — WhatsApp Channel"
#
# Layout (built one phase at a time):
#   config.py        env-var reads + WHATSAPP_ENABLED kill switch   [Phase 1]
#   models.py        WhatsAppContact / WhatsAppMessage / ReportDelivery
#   client.py        outbound: text, document, interactive buttons  [Phase 2]
#   webhook.py       inbound: GET verify + POST receive (HMAC-gated) [Phase 2]
#   urls.py          routing                                        [Phase 2]
#   service.py       inbound text -> ResearchSession -> enqueue     [Phase 3]
#   progress.py      Redis tap -> progress pings                    [Phase 4]
#   delivery.py      summary + document out                         [Phase 4-5]
#   filename.py      query slug -> safe filename                    [Phase 5]
#   state.py         email state machine                            [Phase 6]
#   email_service.py Brevo send with PDF attachment                 [Phase 6]
#
# NOTE: nothing is imported here on purpose. Django loads this package at
# startup; importing client/webhook eagerly would pull `requests` and settings
# reads into every management command, including `migrate`.
