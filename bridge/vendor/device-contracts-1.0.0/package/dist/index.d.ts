import type { Admission, AdmissionResult, Authorization, ReferenceInput } from './types.js';
export type * from './types.js';
export declare const ARTIFACT_VERSION = "1.0.0";
export declare const API_VERSION = "1.0";
export declare const MAX_JSON_DEPTH = 32;
export declare const schema: any;
/** Strict shape validation. Unknown schema names reject rather than widening the contract. */
export declare function validate(definition: string, value: unknown): boolean;
export declare function authorize(input: Authorization): {
    decision: 'allowed' | 'unauthenticated' | 'forbidden';
    effects: 0;
};
/** A pure admission decision. The owner must atomically apply a reservation and retain its receipt. */
export declare function admit(input: Admission): AdmissionResult;
/** Inputs other than request/cursor/renderer are trusted, schema-validated owner state. No I/O occurs. */
export declare function evaluate(input: ReferenceInput): unknown;
