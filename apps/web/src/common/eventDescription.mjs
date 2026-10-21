export const getEventDescription = (event, t, siteTitle) => {
  const action = event?.event_type || ''
  const objectType = event?.referenced_object?.type
  if (!objectType && action.toLowerCase() !== 'joined')
    return event?.description || action

  const translatedAction = t(`dashboard.event_actions.${action.toLowerCase()}`, {defaultValue: action})
  const target = objectType
    ? t(`dashboard.event_objects.${objectType.toLowerCase().replace(/\s+/g, '_')}`, {defaultValue: objectType})
    : siteTitle
  return `${translatedAction} ${target}`.trim()
}
