import type { Admission, AdmissionResult, AdmissionResultV1_1, AdmissionV1_1, ApiVersion, Authorization, ReferenceInput, Snapshot, SnapshotV1_1 } from './types.js';
export type * from './types.js';
export declare const ARTIFACT_VERSION = "1.2.0";
/** The original wire version. 1.0-only consumers keep using it unchanged. */
export declare const API_VERSION = "1.0";
export declare const API_VERSIONS: readonly ["1.0", "1.1"];
/** Moods every device with moments supported must declare. */
export declare const CORE_MOODS: readonly ["celebrate", "setback", "reminder"];
/** A moment may be scheduled at most this far ahead of its delivery. */
export declare const MOMENT_MAX_LEAD_MS = 60000;
/** A device remembers at least this many recent moment IDs per controller clock epoch. */
export declare const MOMENT_MEMORY = 64;
export declare const MAX_JSON_DEPTH = 32;
export declare const schema: any;
/** Strict shape validation. Unknown schema names reject rather than widening the contract. */
export declare function validate(definition: string, value: unknown): boolean;
export declare function authorize(input: Authorization): {
    decision: 'allowed' | 'unauthenticated' | 'forbidden';
    effects: 0;
};
/**
 * The API version a read is served at. No request means 1.0, so 1.0 readers never see 1.1 shapes. Otherwise
 * the controller serves the highest version it has of the same major that is not above the request.
 */
export declare function negotiateApiVersion(requested: unknown, served: readonly ApiVersion[]): {
    decision: 'serve';
    apiVersion: ApiVersion;
} | {
    decision: 'invalid-request';
};
/** A pure admission decision. The owner must atomically apply a reservation and retain its receipt. */
export declare function admit(input: Admission): AdmissionResult;
/** A 1.1 controller also admits 1.1 envelopes; each receipt carries its request's API version. */
export declare function admit(input: AdmissionV1_1): AdmissionResultV1_1;
export declare function admit(input: Admission | AdmissionV1_1): AdmissionResultV1_1;
/** The 1.0 view a 1.1 controller serves to a 1.0 reader: moment content is omitted, never misrepresented. */
export declare function downgradeSnapshot(snapshot: SnapshotV1_1): Snapshot;
/** Inputs other than request/cursor/renderer are trusted, schema-validated owner state. No I/O occurs. */
export declare function evaluate(input: ReferenceInput): unknown;
export { INSTALL_RECEIPT_VERSION, installReceiptSchema, validateInstallReceipt } from './install-receipt.js';
