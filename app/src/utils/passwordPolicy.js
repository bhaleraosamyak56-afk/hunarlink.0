/**
 * Standard HunarLink Password Policy & Live Checklist Evaluator.
 * Minimum 8 characters + uppercase + lowercase + number + special symbol (no spaces).
 */
export const MIN_PASSWORD_LENGTH = 8;

export const PASSWORD_RULES = [
  {
    id: 'length',
    label: 'At least 8 characters',
    test: (pwd) => pwd.length >= MIN_PASSWORD_LENGTH
  },
  {
    id: 'uppercase',
    label: 'At least 1 uppercase letter (A–Z)',
    test: (pwd) => /[A-Z]/.test(pwd)
  },
  {
    id: 'lowercase',
    label: 'At least 1 lowercase letter (a–z)',
    test: (pwd) => /[a-z]/.test(pwd)
  },
  {
    id: 'number',
    label: 'At least 1 number (0–9)',
    test: (pwd) => /[0-9]/.test(pwd)
  },
  {
    id: 'symbol',
    label: 'At least 1 special symbol (!@#$%^&*…)',
    test: (pwd) => /[^A-Za-z0-9\s]/.test(pwd)
  },
  {
    id: 'nospace',
    label: 'No spaces',
    test: (pwd) => pwd.length > 0 && !/\s/.test(pwd)
  }
];

export function evaluatePassword(password) {
  const pwd = String(password || '');
  const results = PASSWORD_RULES.map((rule) => ({
    id: rule.id,
    label: rule.label,
    passed: rule.test(pwd)
  }));
  const passedCount = results.filter((r) => r.passed).length;
  const isValid = results.every((r) => r.passed);

  let strengthLabel = 'Empty';
  let strengthColor = '#cbd5e1';
  if (pwd.length > 0) {
    if (passedCount <= 2) {
      strengthLabel = 'Weak';
      strengthColor = '#b91c1c';
    } else if (passedCount <= 4) {
      strengthLabel = 'Fair';
      strengthColor = '#d97706';
    } else if (!isValid) {
      strengthLabel = 'Almost there';
      strengthColor = '#2563eb';
    } else {
      strengthLabel = pwd.length >= 12 ? 'Very Strong' : 'Strong';
      strengthColor = '#15803d';
    }
  }

  return {
    isValid,
    passedCount,
    totalRules: results.length,
    strengthLabel,
    strengthColor,
    results,
    errorMessage: isValid
      ? ''
      : 'Password must be at least 8 characters and include 1 uppercase letter, 1 lowercase letter, 1 number, 1 special symbol, and no spaces.'
  };
}
