/** Provisional artifacts are valid only for their exact schema epoch. */
export interface CompiledQueryArtifact {
  epoch: number;
  is_pure: boolean;
  rhai_script: string;
}
export type SSEEvent =
  | { type: "SYNC_TOKEN"; payload: { actionId: string; esOffset: number } }
  | { type: "SCHEMA_ADVANCED"; payload: { projectId: string; newEpoch: number; diff: unknown[] } }
  | { type: "SAGA_PROGRESS"; payload: { sagaId: string; completed: number; total: number } };
