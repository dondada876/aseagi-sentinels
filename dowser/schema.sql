-- gap-sentinel — additive, NON-DESTRUCTIVE. Records the delta/gap verdict per claim, the proposed
-- corroboration candidates found in the communication corpora, and the evidence-request directives
-- for gaps with no corroborator. Never mutates canonical_facts. Promotion of a candidate into a
-- confirmed foundation is a separate, authorized step (human confirms the link before it counts).

CREATE TABLE IF NOT EXISTS evidence_gap (
  gap_id       text PRIMARY KEY,           -- sha1(run_id|fact_id)
  run_id       text NOT NULL,
  fact_id      text NOT NULL,
  delta_class  text NOT NULL,              -- SUBSTANTIATED | THIN | OPEN_GAP | CONTRADICTED
  event_date   date,
  parties      text[],
  keywords     text[],
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gap_class ON evidence_gap(delta_class);

CREATE TABLE IF NOT EXISTS corroboration_candidate (
  candidate_id text PRIMARY KEY,           -- sha1(fact_id|msg_hash)
  run_id       text NOT NULL,
  fact_id      text NOT NULL,
  source       text,                       -- comms | police | medical | court | ...
  ref_hash     text,                       -- message_hash / doc hash of the corroborator
  sender       text, recipient text, ref_date timestamptz,
  score        numeric,                    -- 0..1 (party + date-proximity + keyword overlap)
  matched_kw   text[],
  excerpt      text,
  status       text DEFAULT 'PROPOSED_FOUNDATION',  -- PROPOSED_FOUNDATION | CONFIRMED | REJECTED
  created_at   timestamptz DEFAULT now(),
  UNIQUE (fact_id, ref_hash)
);
CREATE INDEX IF NOT EXISTS idx_cand_fact ON corroboration_candidate(fact_id);

CREATE TABLE IF NOT EXISTS evidence_request (
  request_id    text PRIMARY KEY,          -- sha1(run_id|fact_id)
  run_id        text NOT NULL,
  fact_id       text NOT NULL,
  event         text,
  event_date    date,
  target_agency text,                      -- police | da | cfs | court | medical | comms
  record_sought text,
  mechanism     text,                      -- CPRA / subpoena / W&I 827 / FRCP 34/45 / ...
  parties       text[],
  fulfilled     boolean DEFAULT false,
  created_at    timestamptz DEFAULT now()
);

CREATE OR REPLACE VIEW v_sentinel_status AS
SELECT delta_class, count(*) AS n FROM evidence_gap GROUP BY 1 ORDER BY 1;
