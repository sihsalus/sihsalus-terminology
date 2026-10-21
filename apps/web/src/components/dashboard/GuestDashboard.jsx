import React from 'react';
import { useTranslation } from 'react-i18next';
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import APIService from '../../services/APIService'
import DashboardEvents from './DashboardEvents';
import EventsButtonGroup from './EventsButtonGroup';
import DashboardBanners from './DashboardBanners'
import CommunityBlog from './CommunityBlog'
import EmptyOverview from '../repos/RepoEmptyOverview'
import Button from '../common/Button';
import { getLoginURL } from '../../common/utils'


const GuestDashboard = () => {
  const { t } = useTranslation()
  const [allEvents, setAllEvents] = React.useState({events: [], headers: {}})
  const [scope, setScope] = React.useState('all')
  const [loading, setLoading] = React.useState(true)

  const getService = (page, limit=10) => APIService.new().overrideURL('/events/').get(null, null, {limit: limit, page: page})

  const fetchEvents = () => {
    setLoading(true)
    getService(parseInt(allEvents.headers.page_number || '0') + 1).then(response => {
      setAllEvents({events: [...allEvents.events, ...response.data], headers: response.headers})
      setLoading(false)
    })
  }

  const onScopeChange = newScope => {
    if(newScope === scope)
      return
    setScope(newScope)

    if(newScope === 'all')
      !allEvents.events.length && fetchEvents()
  }


  React.useEffect(() => {
    fetchEvents()
  }, [])

  const getScopeEvents = () => {
    if(scope === 'orgs')
      return []
    if(scope === 'following')
      return []
    return allEvents.events
  }


  return (
    <Box sx={{display: 'grid', gridTemplateColumns: {xs: 'minmax(0, 1fr)', lg: 'minmax(0, 1fr) 360px'}, gap: 2, width: '100%', alignItems: 'start'}}>
      <Box sx={{minWidth: 0}}>
        <Box sx={{display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1}}>
          <Typography sx={{fontSize: '22px', color: 'secondary.main'}}>
            {(t('dashboard.anonymous_heading'))}
          </Typography>
          <EventsButtonGroup selected={scope} onClick={onScopeChange} />
        </Box>
        {
          ['all', 'highlights'].includes(scope) ?
            <DashboardEvents events={getScopeEvents()} sx={{marginTop: '16px'}} highlight isLoading={loading} />:
          <Box sx={{minHeight: 'min(400px, calc(var(--app-height) - var(--app-header-height, 64px) - 96px))', py: 3, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', textAlign: 'center', '& svg': {maxWidth: '100%'}}}>
            <EmptyOverview
              label={t('dashboard.events_scope_sign_in')}
              action={
                <Button className='no-anchor-styles' label={t('auth.sign_in')} sx={{ backgroundColor: 'primary.main', maxWidth: '100%', minWidth: '92px', color: '#FFF !important', marginTop: '16px' }} href='#' onClick={e => { e.preventDefault(); getLoginURL().then(url => { window.location.href = url }) }} component='a' />
              }
            />
          </Box>
        }
      </Box>
      <Box sx={{minWidth: 0}}>
        <DashboardBanners />
        <CommunityBlog sx={{marginTop: '8px'}} />
      </Box>
    </Box>
  )
}

export default GuestDashboard
