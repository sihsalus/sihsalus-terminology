import assert from 'node:assert/strict'
import test from 'node:test'
import {getEventDescription} from '../common/eventDescription.mjs'

const labels = {
  'dashboard.event_actions.created': 'creó',
  'dashboard.event_actions.joined': 'se unió a',
  'dashboard.event_actions.released': 'publicó',
  'dashboard.event_objects.organization': 'una organización',
  'dashboard.event_objects.source_version': 'una versión de fuente',
}
const t = (key, {defaultValue}) => labels[key] || defaultValue

test('translates activity actions and organization articles', () => {
  assert.equal(getEventDescription({event_type: 'Created', referenced_object: {type: 'Organization'}}, t, 'SIHSALUS'), 'creó una organización')
})

test('translates multiword resource types without changing identifiers', () => {
  const event = {event_type: 'Released', referenced_object: {type: 'Source Version', id: '2026-10'}}
  assert.equal(getEventDescription(event, t, 'SIHSALUS'), 'publicó una versión de fuente')
  assert.equal(event.referenced_object.id, '2026-10')
})

test('uses the local site title when a user joins the installation', () => {
  assert.equal(getEventDescription({event_type: 'Joined', referenced_object: null}, t, 'SIHSALUS Terminología'), 'se unió a SIHSALUS Terminología')
})

test('preserves unknown activity and resource labels from the API', () => {
  assert.equal(getEventDescription({event_type: 'Imported', referenced_object: {type: 'External Catalog'}}, t, 'SIHSALUS'), 'Imported External Catalog')
  assert.equal(getEventDescription({event_type: 'Removed', description: 'Removed archived resource'}, t, 'SIHSALUS'), 'Removed archived resource')
})
