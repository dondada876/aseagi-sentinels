-- reanchor — additive, NON-DESTRUCTIVE anchor store. The engine writes PROPOSED anchors here;
-- it never mutates canonical_facts or statement_certification. A separate, authorized promotion
-- step copies auth_status='RESOLVED_EXACT' + grid_status='GRID_SET' anchors into
-- statement_certification (where cert_guard then enforces the physical-location rule).

CREATE TABLE IF NOT EXISTS statement_anchor (
  anchor_id      text PRIMARY KEY,          -- sha1(fact_id|twin_udid|page|char_start)
  run_id         text NOT NULL,
  fact_id        text NOT NULL,             -- FK-in-spirit to canonical_facts.fact_id (not enforced: agnostic)
  twin_udid      text NOT NULL,
  page           integer NOT NULL,
  char_start     integer,
  char_end       integer,
  match_method   text,                      -- EXACT | NORMALIZED | FUZZY
  match_score    numeric,                   -- 0..1
  auth_status    text NOT NULL,             -- RESOLVED_EXACT | PROPOSED_FUZZY | AMBIGUOUS | UNRESOLVED
  grid_status    text NOT NULL,             -- GRID_SET | PENDING_BBOX
  grid_address   text,                      -- e.g. 'C2'  (from twinkit grid template)
  grid_template  text,
  bbox_norm      numeric[],                 -- [x0,y0,x1,y1] in [0,1]
  verifier       text,                      -- who proposed (verifier-independent from the extractor)
  promoted       boolean DEFAULT false,     -- copied into statement_certification yet?
  created_at     timestamptz DEFAULT now(),
  UNIQUE (fact_id, twin_udid, page, char_start)
);
CREATE INDEX IF NOT EXISTS idx_anchor_fact ON statement_anchor(fact_id);
CREATE INDEX IF NOT EXISTS idx_anchor_auth ON statement_anchor(auth_status, grid_status);

-- at-a-glance status of the re-anchoring effort
CREATE OR REPLACE VIEW v_reanchor_status AS
SELECT auth_status, grid_status, count(*) AS n,
       round(avg(match_score)::numeric, 3) AS avg_score
FROM statement_anchor GROUP BY 1, 2 ORDER BY 1, 2;

-- the promotion candidates (fully authenticated + spatially anchored, not yet promoted)
CREATE OR REPLACE VIEW v_reanchor_promotable AS
SELECT * FROM statement_anchor
WHERE auth_status = 'RESOLVED_EXACT' AND grid_status = 'GRID_SET' AND promoted = false;
