import React from 'react'
import { useTranslation } from 'react-i18next';
import startCase from 'lodash/startCase'
import DoneIcon from '@mui/icons-material/Done';
import ButtonGroup from '@mui/material/ButtonGroup'
import Button from '@mui/material/Button'

const EventButton = ({ label, selected, terminal, onClick }) => {
  return (
    <Button aria-pressed={selected} sx={[{
      textTransform: 'none',
      fontWeight: 'bold',
      minWidth: 0,
      flex: '1 1 auto',
      whiteSpace: 'normal',
      lineHeight: 1.4,
      px: 1,
      '& .MuiButton-startIcon': {ml: 0, mr: 0.5}
    }, selected ? {
      backgroundColor: 'surface.s90'
    } : {
      backgroundColor: ''
    }, terminal ? {
      borderRadius: '25px'
    } : {
      borderRadius: null
    }]} color='secondary' startIcon={selected ? <DoneIcon fontSize='inherit' /> : undefined} onClick={onClick}>
      {label}
    </Button>
  );
}
const EventsButtonGroup = ({ onClick, selected }) => {
  const { t } = useTranslation()
  return (
    <ButtonGroup size="small" aria-label={t('dashboard.activity_filters')} color='secondary' sx={{maxWidth: '100%', width: {xs: '100%', sm: 'auto'}}}>
      <EventButton label={t('common.all')} selected={selected === 'all'} terminal onClick={() => onClick('all')} />
      <EventButton label={t('common.following')} selected={selected === 'following'} onClick={() => onClick('following')} />
      <EventButton label={startCase(t('org.my'))} selected={selected === 'orgs'} terminal onClick={() => onClick('orgs')} />
    </ButtonGroup>
  )
}
export default EventsButtonGroup;
