# How to send a real WhatsApp chat export (Genius Kids pilot)

The parser and pipeline are built and tested, but on synthetic data.
We need one real export to validate end to end before go-live.

## Supervisor steps (Mario or Paul), 60 seconds on the phone

1. Open the Genius Kids job WhatsApp chat.
2. Tap the chat name at the top.
3. Scroll down, tap "Export Chat".
4. Choose "Without Media" (faster; media markers are handled).
5. Send the .txt to joseph@yourcompany.example.com, or drop it in this inbox
   folder: Site Diary/field_exports/inbox/

## What happens next

Cowork parses it with whatsapp_parser.py, dedupes on msg_id, lands rows
in RAW_MESSAGES, then the site-diary skill extracts the diary, labor,
quantities, delays, and tasks. Supplier names (if any) stay internal.
