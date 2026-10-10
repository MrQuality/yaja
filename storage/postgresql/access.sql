-- Trusted backend capability; these row locks do not authenticate end users.
CREATE FUNCTION kehila.lock_actor(kehila.ident) RETURNS SETOF kehila.actors
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, kehila, pg_temp AS $$
  SELECT a.* FROM kehila.actors a WHERE a.actor_id = $1 FOR NO KEY UPDATE;
$$;
CREATE FUNCTION kehila.lock_operation(bigint) RETURNS SETOF kehila.operations
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, kehila, pg_temp AS $$
  SELECT o.* FROM kehila.operations o WHERE o.operation_row_id = $1 FOR SHARE;
$$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA kehila FROM PUBLIC;
GRANT USAGE ON SCHEMA kehila TO kehila_creator;
GRANT USAGE ON TYPE kehila.ident, kehila.u64, kehila.operation_token TO kehila_creator;
GRANT SELECT ON kehila.actors TO kehila_creator;
GRANT SELECT, INSERT ON kehila.operations, kehila.operation_payloads TO kehila_creator;
GRANT USAGE ON SEQUENCE kehila.operations_operation_row_id_seq TO kehila_creator;
GRANT EXECUTE ON FUNCTION kehila.lock_actor(kehila.ident),
  kehila.lock_operation(bigint) TO kehila_creator;
