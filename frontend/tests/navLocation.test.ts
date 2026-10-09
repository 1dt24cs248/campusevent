import assert from 'node:assert/strict';
import test from 'node:test';
import { floorLabel } from '../src/features/user/navLocation.ts';

test('labels level -1 as Basement', () => {
  assert.equal(floorLabel({ level: -1, name: '-1st Floor' }), 'Basement');
});

test('uses real labels and ordinal labels for actual recorded levels', () => {
  assert.equal(floorLabel({ level: 0, name: 'Ground' }), 'Ground Floor');
  assert.equal(floorLabel({ level: 1, name: 'Floor 1' }), '1st Floor');
  assert.equal(floorLabel({ level: 2, name: 'Floor 2' }), '2nd Floor');
  assert.equal(floorLabel({ level: 3, name: 'Floor 3' }), '3rd Floor');
  assert.equal(floorLabel({ level: 12, name: 'Floor 12' }), '12th Floor');
  assert.equal(floorLabel({ level: 4, label: 'Upper level', name: 'Floor 4' }), 'Upper level');
});
