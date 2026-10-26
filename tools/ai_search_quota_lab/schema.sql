-- OFFLINE EXPERIMENT ONLY. Apply inside a fresh disposable test schema.
-- No application migration, provider, identity or retention policy is installed.
CREATE TABLE ai_usage_days (
    subject_kind text NOT NULL CHECK (subject_kind IN ('guest', 'auth')),
    subject_id uuid NOT NULL,
    madrid_date date NOT NULL,
    quota_limit integer GENERATED ALWAYS AS
        (CASE subject_kind WHEN 'guest' THEN 3 ELSE 200 END) STORED,
    used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
    reserved integer NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    PRIMARY KEY (subject_kind, subject_id, madrid_date),
    CHECK (used + reserved <= quota_limit)
);

CREATE TABLE ai_search_requests (
    subject_kind text NOT NULL,
    subject_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash text NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    madrid_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('reserved', 'running', 'succeeded', 'failed')),
    fence bigint NOT NULL DEFAULT 0 CHECK (fence >= 0),
    lease_until timestamptz NOT NULL,
    result jsonb,
    failure_code text,
    PRIMARY KEY (subject_kind, subject_id, idempotency_key),
    FOREIGN KEY (subject_kind, subject_id, madrid_date)
        REFERENCES ai_usage_days (subject_kind, subject_id, madrid_date),
    CHECK ((status = 'succeeded') = (result IS NOT NULL)),
    CHECK ((status = 'failed') = (failure_code IS NOT NULL))
);
CREATE INDEX ai_search_requests_expiry ON ai_search_requests (lease_until)
    WHERE status IN ('reserved', 'running');

CREATE FUNCTION madrid_window(p_at timestamptz)
RETURNS TABLE (day date, reset_at timestamptz)
LANGUAGE sql STABLE STRICT AS $$
    SELECT (p_at AT TIME ZONE 'Europe/Madrid')::date,
        (((p_at AT TIME ZONE 'Europe/Madrid')::date + 1)::timestamp
            AT TIME ZONE 'Europe/Madrid');
$$;

-- The hash is server-built from channel + body digest + session/version + contract.
-- Client identity/hash validation and technical abuse limits remain integration gates.
CREATE FUNCTION reserve(p_kind text, p_subject uuid, p_key uuid, p_hash text)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
    v_day date := (clock_timestamp() AT TIME ZONE 'Europe/Madrid')::date;
    v_request ai_search_requests;
    v_usage ai_usage_days;
BEGIN
    IF p_kind NOT IN ('guest', 'auth') OR p_kind IS NULL OR p_subject IS NULL
       OR p_key IS NULL OR p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'INVALID_OPERATION';
    END IF;
    SELECT * INTO v_request FROM ai_search_requests
      WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key;
    IF NOT FOUND THEN
        INSERT INTO ai_usage_days(subject_kind, subject_id, madrid_date)
          VALUES (p_kind, p_subject, v_day) ON CONFLICT DO NOTHING;
        SELECT * INTO v_usage FROM ai_usage_days
          WHERE subject_kind=p_kind AND subject_id=p_subject AND madrid_date=v_day FOR UPDATE;
        -- Recheck after the day lock: concurrent same-key final-slot retry must replay.
        SELECT * INTO v_request FROM ai_search_requests
          WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key;
        IF NOT FOUND THEN
            IF v_usage.used + v_usage.reserved >= v_usage.quota_limit THEN
                RAISE EXCEPTION 'QUOTA_EXHAUSTED';
            END IF;
            INSERT INTO ai_search_requests
              (subject_kind, subject_id, idempotency_key, request_hash, madrid_date, status, lease_until)
              VALUES (p_kind, p_subject, p_key, p_hash, v_day, 'reserved', clock_timestamp()+interval '60 seconds')
              ON CONFLICT DO NOTHING RETURNING * INTO v_request;
            IF FOUND THEN
                UPDATE ai_usage_days SET reserved=reserved+1
                  WHERE subject_kind=p_kind AND subject_id=p_subject AND madrid_date=v_day;
                RETURN jsonb_build_object('action', 'created', 'operation', to_jsonb(v_request));
            END IF;
            -- A simultaneous reservation can belong to the previous Madrid day.
            SELECT * INTO STRICT v_request FROM ai_search_requests
              WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key;
        END IF;
    END IF;
    IF v_request.request_hash <> p_hash THEN RAISE EXCEPTION 'IDEMPOTENCY_CONFLICT'; END IF;
    RETURN jsonb_build_object('action',
        CASE WHEN v_request.status IN ('succeeded','failed') THEN 'replay' ELSE 'inflight' END,
        'operation', to_jsonb(v_request));
END;
$$;

CREATE FUNCTION claim(p_kind text, p_subject uuid, p_key uuid)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_request ai_search_requests;
BEGIN
    UPDATE ai_search_requests SET status='running', fence=fence+1,
        lease_until=clock_timestamp()+interval '60 seconds'
      WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key
        AND status='reserved' AND lease_until > clock_timestamp()
      RETURNING * INTO v_request;
    IF NOT FOUND THEN RAISE EXCEPTION 'CLAIM_REJECTED'; END IF;
    RETURN to_jsonb(v_request);
END;
$$;

-- One DB transaction: persisted synthetic result + counters. AI-08 session CAS
-- must join THIS transaction before this design can be integrated with the app.
-- NULL result means service failure. Clarification has no implementation here.
CREATE FUNCTION finish(p_kind text, p_subject uuid, p_key uuid, p_fence bigint,
                       p_result jsonb, p_failure text DEFAULT NULL, p_recover boolean DEFAULT false)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_request ai_search_requests;
BEGIN
    SELECT * INTO STRICT v_request FROM ai_search_requests
      WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key;
    -- All counter mutations lock day BEFORE operation. Claim never locks a day.
    PERFORM 1 FROM ai_usage_days WHERE subject_kind=p_kind AND subject_id=p_subject
      AND madrid_date=v_request.madrid_date FOR UPDATE;
    SELECT * INTO STRICT v_request FROM ai_search_requests
      WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key FOR UPDATE;
    IF v_request.status IN ('succeeded','failed') THEN RETURN to_jsonb(v_request); END IF;
    IF p_recover IS NULL OR p_fence IS NULL OR v_request.fence <> p_fence THEN
        RAISE EXCEPTION 'STALE_WORKER';
    END IF;
    IF p_recover THEN
        IF v_request.lease_until > clock_timestamp() OR p_result IS NOT NULL THEN
            RAISE EXCEPTION 'RECOVERY_REJECTED';
        END IF;
    ELSIF v_request.status <> 'running' OR v_request.lease_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'STALE_WORKER';
    END IF;
    IF (p_result IS NULL) = (p_failure IS NULL)
       OR (p_failure IS NOT NULL AND p_failure NOT IN ('ASR_FAILURE','LLM_FAILURE','BACKEND_FAILURE','LEASE_EXPIRED')) THEN
        RAISE EXCEPTION 'INVALID_OUTCOME';
    END IF;
    UPDATE ai_usage_days SET reserved=reserved-1, used=used+CASE WHEN p_result IS NULL THEN 0 ELSE 1 END
      WHERE subject_kind=p_kind AND subject_id=p_subject AND madrid_date=v_request.madrid_date;
    UPDATE ai_search_requests SET status=CASE WHEN p_result IS NULL THEN 'failed' ELSE 'succeeded' END,
        result=p_result, failure_code=p_failure, fence=fence+CASE WHEN p_recover THEN 1 ELSE 0 END
      WHERE subject_kind=p_kind AND subject_id=p_subject AND idempotency_key=p_key RETURNING * INTO v_request;
    RETURN to_jsonb(v_request);
END;
$$;
