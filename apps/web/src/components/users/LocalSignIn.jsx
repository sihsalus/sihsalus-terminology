import React from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Box, Button, TextField, Typography } from '@mui/material'
import APIService from '../../services/APIService'
import { consumeOAuthReturnTo } from '../../common/utils'

// The API already supports local accounts when no identity provider is configured.
const LocalSignIn = () => {
  const { t } = useTranslation()
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [failed, setFailed] = React.useState(false)

  const submit = async event => {
    event.preventDefault()
    if(busy) return
    setBusy(true)
    setFailed(false)
    try {
      const response = await APIService.users().login().request(
        'POST', {username, password}, false, {timeout: 15000})
      const token = response.data?.token
      if(!token) throw new Error('Authentication failed')
      const profile = await APIService.user().request('GET', null, token, {
        timeout: 15000,
        query: {includeSubscribedOrgs: true, includeAuthGroups: true, includePins: true, includeFollowing: true}
      })
      if(!profile.data?.username) throw new Error('Profile unavailable')
      localStorage.removeItem('id_token')
      localStorage.removeItem('server_configs')
      localStorage.setItem('user', JSON.stringify(profile.data))
      localStorage.setItem('token', token)
      sessionStorage.removeItem('session_expired')
      const returnTo = consumeOAuthReturnTo()
      // Stay within the hash router; never navigate to an external return URL.
      window.location.hash = '#' + (returnTo?.startsWith('/') ? returnTo : '/')
      window.location.reload()
    } catch {
      setFailed(true)
    } finally {
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <Box component='form' onSubmit={submit} sx={{maxWidth: 400, mx: 'auto', my: 6, p: 3, display: 'grid', gap: 2}}>
      <Typography component='h1' variant='h5'>{t('auth.sign_in')}</Typography>
      <Typography>{t('auth.managed_accounts')}</Typography>
      {failed && <Alert severity='error'>{t('auth.local_sign_in_error')}</Alert>}
      <TextField label={t('auth.username')} name='username' autoComplete='username' required
        value={username} onChange={event => setUsername(event.target.value)} disabled={busy} />
      <TextField label={t('auth.password')} name='password' type='password' autoComplete='current-password' required
        value={password} onChange={event => setPassword(event.target.value)} disabled={busy} />
      <Button variant='contained' type='submit' disabled={busy}>
        {t(busy ? 'auth.signing_in' : 'auth.sign_in')}
      </Button>
    </Box>
  )
}

export default LocalSignIn
