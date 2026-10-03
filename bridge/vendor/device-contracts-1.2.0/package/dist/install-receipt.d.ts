export declare const INSTALL_RECEIPT_VERSION = "install-receipt/1.0";
export declare const installReceiptSchema: any;
/** Validates receipt shape and cross-field evidence consistency, without inspecting a host. */
export declare function validateInstallReceipt(value: unknown): boolean;
