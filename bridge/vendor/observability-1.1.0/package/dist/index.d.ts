export declare const ARTIFACT_VERSION = "1.1.0";
export declare const SCHEMA_VERSION = "1.1";
export declare const SEMANTIC_CONVENTIONS_VERSION = "1.44.0";
export declare const MAX_RECORD_BYTES = 8192;
export declare const MAX_QUEUE_RECORDS = 1024;
export declare const MAX_QUEUE_BYTES: number;
export declare const MAX_FLUSH_MS = 1000;
export type Primitive = string | number | boolean;
export type TraceContext = Readonly<{
    trace_id: string;
    span_id: string;
    trace_flags: string;
}>;
export type DiagnosticRecord = {
    schema_version: '1.0' | '1.1';
    timestamp?: string;
    observed_timestamp?: string;
    severity_number: number;
    severity_text: string;
    event_name: string;
    body: string;
    resource: Record<string, string>;
    scope: {
        name: string;
        version: string;
    };
    attributes: Record<string, Primitive>;
    trace_id?: string;
    span_id?: string;
    trace_flags?: string;
};
export type Result<T> = {
    ok: true;
    value: T;
} | {
    ok: false;
    code: 'invalid-record';
};
export declare const catalog: Readonly<{
    artifact_version: string;
    schema_versions: string[];
    default_schema_version: string;
    semantic_conventions: string;
    events: {
        "process.started": string;
        "process.stopped": string;
        "process.failed": string;
        "command.admitted": string;
        "command.rejected": string;
        "command.queued": string;
        "command.executing": string;
        "command.completed": string;
        "command.cancelled": string;
        "lifecycle.observed": string;
        "feed.changed": string;
        "operation.completed": string;
        "operation.failed": string;
        "telemetry.dropped": string;
    };
    services: string[];
    scopes: string[];
    severities: {
        TRACE: number;
        DEBUG: number;
        INFO: number;
        WARN: number;
        ERROR: number;
        FATAL: number;
    };
    pino_levels: {
        "10": string;
        "20": string;
        "30": string;
        "40": string;
        "50": string;
        "60": string;
    };
    python_levels: {
        "5": string;
        "10": string;
        "20": string;
        "30": string;
        "40": string;
        "50": string;
    };
    span_names: string[];
    attributes: {
        "bunny.controller.id": {
            type: string;
            pattern: string;
        };
        "bunny.device.id": {
            type: string;
            pattern: string;
        };
        "bunny.source.id": {
            type: string;
            pattern: string;
        };
        "bunny.request.id": {
            type: string;
            pattern: string;
        };
        "bunny.ticket.epoch": {
            type: string;
            pattern: string;
        };
        "bunny.operation.id": {
            type: string;
            pattern: string;
        };
        "bunny.task.epoch": {
            type: string;
            pattern: string;
        };
        "bunny.effect.epoch": {
            type: string;
            pattern: string;
        };
        "bunny.clock.epoch": {
            type: string;
            pattern: string;
        };
        "bunny.ticket.sequence": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.state.revision": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.source.revision": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.generation": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.telemetry.dropped_count": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.telemetry.failure_count": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.duration_ms": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.queue.wait_ms": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.execution.duration_ms": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.operation": {
            enum: string[];
        };
        "bunny.outcome": {
            enum: string[];
        };
        "bunny.reason": {
            enum: string[];
        };
        "bunny.provenance": {
            enum: string[];
        };
        "bunny.observed.service": {
            enum: string[];
        };
        "bunny.queue.depth": {
            type: string;
            minimum: number;
            maximum: number;
        };
        "bunny.write.possible": {
            type: string;
        };
        "bunny.build.revision": {
            type: string;
            pattern: string;
        };
    };
}>;
export declare function validateRecord(input: unknown): Result<DiagnosticRecord>;
export declare function parseRecord(line: unknown): Result<DiagnosticRecord>;
export declare function encodeRecord(input: unknown): string | undefined;
export declare function createRecord(input: unknown): Result<DiagnosticRecord>;
export declare function projectRecord(input: unknown, version: '1.0' | '1.1'): Result<DiagnosticRecord>;
export declare function toOtlp(input: unknown): {
    resourceLogs: Array<{
        resource: unknown;
        scopeLogs: Array<{
            scope: unknown;
            schemaUrl: string;
            logRecords: Array<Record<string, unknown>>;
        }>;
    }>;
} | undefined;
export declare function queryRecords(records: unknown[], query: Record<string, Primitive>): DiagnosticRecord[];
export declare function severityFor(language: 'pino' | 'python', level: number): {
    severity_text: string;
    severity_number: number;
} | undefined;
export declare function parseTraceparent(header: unknown, boundary: {
    authenticated: boolean;
    owned: boolean;
}): TraceContext | undefined;
export declare function traceHeaders(context: TraceContext | undefined, boundary: {
    authenticated: boolean;
    owned: boolean;
}): Record<string, string>;
export declare const noop: Readonly<{
    emit: (_record: unknown) => false;
    close: () => Promise<undefined>;
    counts: () => {
        accepted: number;
        dropped: number;
        failed: number;
        queued: number;
        bytes: number;
    };
}>;
