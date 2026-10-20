import React from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Box, Button, Typography } from '@mui/material'
import APIService from '../../services/APIService'

// Confirm explicitly so opening an email link alone does not consume its token.
const LocalEmailVerification = ({match}) => {
  const { t } = useTranslation()
  const [state, setState] = React.useState('ready')
  const verify = async () => {
    if(state === 'busy') return
    setState('busy')
    try {
      const {username, token} = match.params
      await APIService.users(encodeURIComponent(username)).verify(encodeURIComponent(token))
        .request('GET', null, false, {timeout: 15000})
      setState('verified')
    } catch {
      setState('failed')
    }
  }
  return (
    <Box sx={{maxWidth: 440, mx: 'auto', my: 6, p: 3, display: 'grid', gap: 2}}>
      <Typography component='h1' variant='h5'>{t('auth.verify_email')}</Typography>
      {state === 'verified' ? <Alert severity='success'>{t('auth.email_verified_sign_in')}</Alert> : <>
        <Typography>{t('auth.verify_email_help')}</Typography>
        {state === 'failed' && <Alert severity='error'>{t('auth.verify_email_error')}</Alert>}
        <Button variant='contained' onClick={verify} disabled={state === 'busy'}>{t('auth.verify_email')}</Button>
      </>}
      <Button href='#/signin'>{t('auth.sign_in')}</Button>
    </Box>
  )
}

export default LocalEmailVerification
