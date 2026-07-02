-- Your Company Staff Training Portal - enable Module 31 (Shop QC Software)
-- Run in the Supabase SQL editor AFTER 01/02/03 are already in place.
-- Safe to re-run (idempotent). Lives only in Postgres; the browser never sees the key.

-- 1) Register the module in the locked prerequisite chain (ord 31, after supervising).
insert into public.module_order (module_id, ord, title) values
  ('shopqc-quality', 31, 'Shop QC Software')
on conflict (module_id) do nothing;

-- 2) Hidden answer key for the Final Knowledge Check (q_index is 0-based).
--    Order matches the questions in site/shopqc-quality.html NC_GATE.
insert into public.module_answers (module_id, q_index, correct_idx) values
  ('shopqc-quality', 0, 1),  -- gate order: Receiving, Fabrication, Release
  ('shopqc-quality', 1, 2),  -- only the lowest unsigned floor step
  ('shopqc-quality', 2, 1),  -- field 8 requires a CWI name
  ('shopqc-quality', 3, 2),  -- CEO co-sign must read exactly The Owner
  ('shopqc-quality', 4, 1)   -- close the NCR on the NCR Log tab
on conflict (module_id, q_index) do nothing;

-- After this runs, the M31 Final Knowledge Check grades server-side like every other module.
-- Note: claim_certificate (if ever enabled) now requires 31 modules complete, not 30.
