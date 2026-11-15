/** Uniform error body (SRS 3.1.4): code, message, optional field errors. */
export class ApiError extends Error {
  constructor(code, message, fields = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.fields = fields;
  }
}
