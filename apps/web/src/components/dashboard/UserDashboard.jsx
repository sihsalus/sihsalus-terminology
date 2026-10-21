/*eslint no-process-env: 0*/

import React from 'react';
import { useTranslation } from 'react-i18next';
import upperFirst from 'lodash/upperFirst'
import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Stack from '@mui/material/Stack'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import APIService from '../../services/APIService'
import { WHITE, SURFACE_COLORS } from '../../common/colors'
import Events from '../common/Events'
import DashboardEvents from './DashboardEvents';
import EventsButtonGroup from './EventsButtonGroup';
import CommunityBlog from './CommunityBlog'


const UsageWidget = ({ username }) => {
  const { t } = useTranslation()

  /*eslint no-undef: 0*/
  const analyticsUrl = window.ANALYTICS_API || process.env.ANALYTICS_API
  const [summary, setSummary] = React.useState(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    if (!analyticsUrl || !username) {
      setLoading(false)
      return
    }
    const now = new Date()
    const start = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    const endStr = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`

    const service = APIService.new()
    service.URL = `${analyticsUrl}/users/${encodeURIComponent(username)}/api-transactions/summary/?timestamp_gte=${start}&timestamp_lte=${endStr}`
    service.get().then(response => {
      setSummary(response.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [analyticsUrl, username])

  if (!analyticsUrl) return null

  const topOp = summary?.top_operations?.[0]

  return (
    <Card
      sx={{ borderRadius: '10px', border: `1px solid ${"var(--SURFACE_COLORS-nv80)"}`, mb: 1 }}
      style={{
        "--SURFACE_COLORS-nv80": SURFACE_COLORS.nv80
      }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography
          variant="subtitle2"
          sx={{
            color: "text.secondary",
            mb: 1
          }}>
          {t('dashboard.usage_title')}
        </Typography>
        {loading ? (
          <Stack
            sx={{
              alignItems: "center",
              py: 1
            }}><CircularProgress size={20} /></Stack>
        ) : summary ? (
          <Stack spacing={0.5}>
            <Stack direction="row" sx={{
              justifyContent: "space-between", gap: 1, flexWrap: 'wrap'
            }}>
              <Typography variant="body2">{t('dashboard.api_requests')}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>{(summary.total_requests || 0).toLocaleString()}</Typography>
            </Stack>
            {topOp && (
              <Stack direction="row" sx={{
                justifyContent: "space-between", gap: 1, flexWrap: 'wrap'
              }}>
                <Typography variant="body2">{t('dashboard.top_operation')}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, overflowWrap: 'anywhere' }}>{topOp.operation_type}</Typography>
              </Stack>
            )}
            <Button
              size="small"
              href={`#/users/${username}/usage`}
              sx={{ textTransform: 'none', mt: 0.5, alignSelf: 'flex-start', p: 0 }}
            >
              {t('dashboard.view_usage')}
            </Button>
          </Stack>
        ) : (
          <Typography variant="body2" sx={{
            color: "text.secondary"
          }}>{t('dashboard.no_usage')}</Typography>
        )}
      </CardContent>
    </Card>
  );
}
const UserDashboard = ({ user }) => {
  const { t } = useTranslation()
  const [selfEvents, setSelfEvents] = React.useState({events: [], headers: {}})
  const [allEvents, setAllEvents] = React.useState({events: [], headers: {}})
  const [followingEvents, setFollowingEvents] = React.useState({events: [], headers: {}})
  const [orgsEvents, setOrgsEvents] = React.useState({events: [], headers: {}})
  const [scope, setScope] = React.useState('all')
  const [loading, setLoading] = React.useState(true)
  const getService = (scope, page, limit=10) => APIService.users(user.username).appendToUrl('events/').get(null, null, {scopes: scope, limit: limit, page: page})
  const fetchEventsForSelf = () => {
    getService('self', parseInt(selfEvents.headers.page_number || '0') + 1, 5).then(response => {
      setSelfEvents({events: [...selfEvents.events, ...response.data], headers: response.headers})
    })
  }
  const fetchEventsForAll = () => {
    setLoading(true)
    getService('following,orgs', parseInt(allEvents.headers.page_number || '0') + 1).then(response => {
      setAllEvents({events: [...allEvents.events, ...response.data], headers: response.headers})
      setLoading(false)
    })
  }
  const fetchEventsForFollowing = () => {
    setLoading(true)
    getService('following', parseInt(followingEvents.headers.page_number || '0') + 1).then(response => {
      setFollowingEvents({events: [...followingEvents.events, ...response.data], headers: response.headers})
      setLoading(false)
    })
  }
  const fetchEventsForOrgs = () => {
    setLoading(true)
    getService('orgs', parseInt(orgsEvents.headers.page_number || '0') + 1).then(response => {
      setOrgsEvents({events: [...orgsEvents.events, ...response.data], headers: response.headers})
      setLoading(false)
    })
  }
  const onScopeChange = newScope => {
    if(newScope === scope)
      return
    setScope(newScope)
    if(newScope === 'all')
      !allEvents.events.length && fetchEventsForAll()
    if(newScope === 'following')
      !followingEvents.events.length && fetchEventsForFollowing()
    if(newScope === 'orgs')
      !orgsEvents.events.length && fetchEventsForOrgs()
  }
  React.useEffect(() => {
    fetchEventsForAll()
    fetchEventsForSelf()
  }, [])
  const getScopeEvents = () => {
    if(scope === 'orgs')
      return orgsEvents.events
    if(scope === 'following')
      return followingEvents.events
    return allEvents.events
  }
  return (
    <Box sx={{display: 'grid', gridTemplateColumns: {xs: 'minmax(0, 1fr)', lg: 'minmax(0, 1fr) 360px'}, gap: 2, width: '100%', alignItems: 'start'}}>
      <Box sx={{minWidth: 0}}>
        <Box sx={{mt: 1, display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 1}}>
          <Typography sx={{fontSize: '22px', color: 'secondary.main'}}>
            {upperFirst(t('dashboard.anonymous_heading'))}
          </Typography>
          <EventsButtonGroup selected={scope} onClick={onScopeChange} />
        </Box>
        <DashboardEvents isLoading={loading} events={getScopeEvents()} />
      </Box>
      <Box sx={{minWidth: 0}}>
        <Box sx={{display: 'flow-root', px: 2, background: WHITE, borderRadius: '10px', border: `1px solid ${SURFACE_COLORS.nv80}`}}>
          <Events user={user} events={selfEvents.events} onLoadMore={selfEvents.headers?.next ? fetchEventsForSelf : false} showAvatar maxHeight="245px" dashboard />
        </Box>
        <Box sx={{mt: 1}}>
          <UsageWidget username={user?.username} />
        </Box>
        <CommunityBlog sx={{marginTop: '8px'}} />
      </Box>
    </Box>
  )
}
export default UserDashboard
