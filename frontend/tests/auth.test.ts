import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validateRegistration } from '../src/pages/Auth';

test('registration validation mirrors the API rules', () => {
  assert.deepEqual(validateRegistration({ display_name: 'Asha', email: 'asha@example.org', password: 'long-enough-pw' }), {});
  const e = validateRegistration({ display_name: '  ', email: 'not-an-email', password: 'short' });
  assert.equal(e.display_name, 'Enter your name');
  assert.equal(e.email, 'Enter a valid email address');
  assert.equal(e.password, 'Use at least 10 characters');
  assert.equal(validateRegistration({ display_name: 'x'.repeat(121), email: 'a@b.co', password: 'x'.repeat(10) }).display_name, 'Use at most 120 characters');
});
