import assert from 'node:assert/strict';
import test from 'node:test';
import { isValidationRecord } from '../src/features/management/academicRecordProvenance.ts';

test('marks explicit synthetic records as validation data', () => {
  assert.equal(isValidationRecord(true, null), true);
});

test('marks synthetic and validation provenance without a boolean flag', () => {
  assert.equal(isValidationRecord(false, 'SYNTHETIC_IMPORT'), true);
  assert.equal(isValidationRecord(false, 'validation fixture'), true);
});

test('does not label genuine or unrelated provenance as synthetic', () => {
  assert.equal(isValidationRecord(false, 'OWNER_SUPPLIED'), false);
  assert.equal(isValidationRecord(false, 'CURATED_CAMPUS_DATA'), false);
  assert.equal(isValidationRecord(false, 'NOT_SYNTHETIC'), false);
  assert.equal(isValidationRecord(false, null), false);
});
