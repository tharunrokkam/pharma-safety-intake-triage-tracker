-- Pharma Safety Intake & Triage Tracker - long-term memory (SQLite)
-- Synthetic data only. No patient identifiers are modelled anywhere.

CREATE TABLE IF NOT EXISTS ref_counters (
    year     INTEGER PRIMARY KEY,
    last_seq INTEGER NOT NULL CHECK (last_seq BETWEEN 0 AND 9999)
);

CREATE TABLE IF NOT EXISTS reports (
    ref_id        TEXT PRIMARY KEY
                  CHECK (ref_id GLOB 'REF-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]'),
    report_type   TEXT NOT NULL
                  CHECK (report_type IN ('Suspected Adverse Event', 'Product Quality Complaint')),
    product_name  TEXT NOT NULL,
    batch_id      TEXT NOT NULL CHECK (batch_id GLOB 'LOT-[0-9][0-9][0-9][0-9][0-9]'),
    date_received TEXT NOT NULL,
    reporter_type TEXT NOT NULL,
    description   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'New' CHECK (status IN ('New', 'In Review', 'Closed')),
    created_by    TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS ix_reports_type ON reports(report_type);

CREATE TABLE IF NOT EXISTS ae_details (
    ref_id            TEXT PRIMARY KEY REFERENCES reports(ref_id),
    event_description TEXT NOT NULL,
    event_onset_date  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_id        TEXT NOT NULL REFERENCES reports(ref_id),
    requested_by  TEXT NOT NULL,
    requested_at  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    reviewer_id   TEXT,
    justification TEXT,
    decided_at    TEXT,
    thread_id     TEXT
);
-- At most one pending closure request per report.
CREATE UNIQUE INDEX IF NOT EXISTS ux_approvals_one_pending ON approvals(ref_id) WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS status_transitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_id      TEXT NOT NULL REFERENCES reports(ref_id),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    actor_id    TEXT NOT NULL,
    approval_id INTEGER REFERENCES approvals(id),
    ts_utc      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc       TEXT NOT NULL,
    actor_id     TEXT NOT NULL,
    action       TEXT NOT NULL,
    ref_id       TEXT,
    from_status  TEXT,
    to_status    TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    prev_hash    TEXT NOT NULL,
    row_hash     TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_audit_ref ON audit_log(ref_id);

-- Immutability: audit_log and status_transitions are append-only.
CREATE TRIGGER IF NOT EXISTS trg_audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_transitions_no_update BEFORE UPDATE ON status_transitions
BEGIN SELECT RAISE(ABORT, 'status_transitions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_transitions_no_delete BEFORE DELETE ON status_transitions
BEGIN SELECT RAISE(ABORT, 'status_transitions is append-only'); END;
