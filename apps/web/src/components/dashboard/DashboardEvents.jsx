import React from 'react';
import { useHistory } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import moment from 'moment'

import Typography from '@mui/material/Typography'
import Box from '@mui/material/Box'
import Card from '@mui/material/Card';
import CardHeader from '@mui/material/CardHeader';
import CardContent from '@mui/material/CardContent';
import Avatar from '@mui/material/Avatar';
import Skeleton from '@mui/material/Skeleton'
import HighlightIcon from '@mui/icons-material/CampaignOutlined';

import isEmpty from 'lodash/isEmpty'

import { WHITE } from '../../common/colors'
import { getSiteTitle } from '../../common/utils'
import { getEventDescription } from '../../common/eventDescription.mjs'
import EntityIcon from '../common/EntityIcon';
import EntityChip from '../common/EntityChip';
import Link from '../common/Link'
import EmptyOverview from '../common/EmptyOverview'

const EventCard = ({ event, highlight }) => {
  const history = useHistory()
  const { t } = useTranslation()
  const getTitle = (event, object, includeSubtitle) => {
    let title = object?.id || object?.username || object?.name
    const subTitle = getEventDescription(event, t, getSiteTitle())
    return (
      <span style={{display: 'flex', flexWrap: 'wrap', alignItems: 'center', columnGap: '4px'}}>
        <Typography component='span' sx={{fontWeight: 'bold', minWidth: 0, maxWidth: '100%'}}>
          <Link label={title} href={'#' + object.url} sx={{color: 'secondary.main', fontSize: '16px', fontWeight: 'bold', minWidth: 0, maxWidth: '100%', overflowWrap: 'anywhere', textAlign: 'left'}} />
        </Typography>
        {
          includeSubtitle &&
            <Typography component='span' sx={{overflowWrap: 'anywhere'}}>
              {subTitle}
            </Typography>
        }
      </span>
    )
  }
  return (
    <Card sx={[{
      boxShadow: 'none',
      border: '1px solid',
      borderColor: 'surface.nv80',
      borderRadius: '10px'
    }, highlight ? {
      margin: '0 0 16px 0'
    } : {
      margin: '16px 0'
    }]}>
      <CardHeader
        sx={{'& .MuiCardHeader-content': {minWidth: 0}}}
        avatar={
          <Avatar sx={{width: '45px', height: '45px', backgroundColor: event.object?.logo_url ? 'transparent' : 'primary.60', cursor: 'pointer'}} onClick={() => history.push(event.object?.version_url || event.object?.url)}>
            <EntityIcon noLink strict entity={event.object} sx={{color: WHITE}} />
          </Avatar>
        }
        title={getTitle(event, event.object, true)}
        subheader={moment(event.created_at).fromNow()}
      />
      {
        event?.referenced_object?.type &&
          <CardContent sx={{backgroundColor: 'surface.main', margin: '0 16px 16px 16px', borderRadius: '10px', padding: '16px !important', display: 'flex', minWidth: 0, borderColor: 'surface.main'}}>
            <EntityChip entity={event.referenced_object} multiLine hideType sx={{color: WHITE, cursor: 'pointer', minWidth: 0, maxWidth: '100%', overflowWrap: 'anywhere'}} onClick={() => history.push(event.referenced_object?.version_url || event.referenced_object?.url)} />
          </CardContent>
      }
    </Card>
  );
}
const HighlightCard = props => {
  const { t } = useTranslation()
  return (
    <Card variant="outlined" sx={{backgroundColor: 'surface.main', marginBottom: '16px', borderRadius: '10px'}}>
      <CardHeader
        sx={{
          color: 'surface.contrastText',
          padding: '16px 16px 12px 16px'
        }}
        avatar={
          <Avatar sx={{backgroundColor: 'transparent'}}>
            <HighlightIcon fontSize='large' sx={{color: 'surface.contrastText'}} />
          </Avatar>
        }
        title={
          <Typography sx={{color: 'surface.contrastText', fontSize: '16px', fontWeight: '500'}}>
            {t('common.highlights')}
          </Typography>
        }
      />
      <CardContent sx={{padding: '0 16px', paddingBottom: '0 !important'}}>
        {props.children}
      </CardContent>
    </Card>
  )
}

const DashboardEvents = ({ events, highlight, sx, isLoading }) => {
  const { t } = useTranslation()
  return (
    <Box sx={{minWidth: 0, maxHeight: {xs: 'none', lg: 'calc(var(--app-height) - var(--app-header-height, 64px) - 96px)'}, overflow: {xs: 'visible', lg: 'auto'}, ...sx}}>
      {
        isLoading ?
          <>
            <Skeleton height={174} sx={{margin: '16px 0', height: '174px', '-webkit-transform': 'none', 'transform': 'none'}} />
            <Skeleton height={174} sx={{margin: '16px 0', height: '174px', '-webkit-transform': 'none', 'transform': 'none'}} />
            <Skeleton height={174} sx={{margin: '16px 0', height: '174px', '-webkit-transform': 'none', 'transform': 'none'}} />
            <Skeleton height={174} sx={{margin: '16px 0', height: '174px', '-webkit-transform': 'none', 'transform': 'none'}} />
            <Skeleton height={174} sx={{margin: '16px 0', height: '174px', '-webkit-transform': 'none', 'transform': 'none'}} />
            </>
            :
        (
          isEmpty(events) ?
            <Box sx={{minHeight: 'min(40vh, 320px)', py: 3, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', textAlign: 'center', '& svg': {maxWidth: '100%'}}}>
              <EmptyOverview label={t('dashboard.no_events')} />
            </Box> :
          (
            events.map(event => (
              highlight ?
                <HighlightCard key={event.id}>
                  <EventCard event={event} highlight={highlight} />
                </HighlightCard> :
              <EventCard key={event.id} event={event} highlight={highlight} />
            ))

          )
        )
      }
    </Box>
  )
}

export default DashboardEvents
