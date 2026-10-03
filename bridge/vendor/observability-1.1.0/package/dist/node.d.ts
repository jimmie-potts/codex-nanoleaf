import { type TraceContext } from './index.js';
export declare class DiagnosticContext {
    #private;
    current(): TraceContext | undefined;
    capture(): TraceContext | undefined;
    run<T>(value: TraceContext | undefined, action: () => T): T;
}
export type SinkOptions = {
    maxRecords?: number;
    maxBytes?: number;
    flushMs?: number;
    minimumSeverity?: number;
};
export type Sink = (line: string) => void | Promise<void>;
/** The injected sink must return promptly; promises may settle asynchronously. */
export declare function createPinoEmitter(sink: Sink, options?: SinkOptions): {
    emit(input: unknown): boolean;
    counts: () => {
        accepted: number;
        dropped: number;
        failed: number;
        queued: number;
        bytes: number;
    };
    close(): Promise<void>;
};
