// SRS Appendix A.1 constants, mirrored for client-side checks.
// The server enforces these too.
export const LIMITS = {
  MAX_MEDS_PER_LIST: 30,
  MAX_IMAGES_PER_LIST: 5,
  MAX_IMAGE_MB: 5,
  MIN_IMAGE_W: 640,
  MIN_IMAGE_H: 480,
  NAME_MIN: 2,
  NAME_MAX: 100,
  PASSWORD_MIN_LEN: 8,
  TOKEN_TTL_MIN: 30,
  MAX_FAILED_LOGINS: 5,
  LOCKOUT_MIN: 15,
};

export const DISCLAIMER =
  "Decision support only. This is not medical advice. " +
  "Discuss these results with your doctor or pharmacist.";

/** SEC-01: at least 8 characters with a letter and a digit. */
export function passwordProblems(password) {
  const problems = [];
  if (password.length < LIMITS.PASSWORD_MIN_LEN) {
    problems.push(`Use at least ${LIMITS.PASSWORD_MIN_LEN} characters.`);
  }
  if (!/[A-Za-z]/.test(password)) problems.push("Include at least one letter.");
  if (!/\d/.test(password)) problems.push("Include at least one number.");
  return problems;
}

export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
