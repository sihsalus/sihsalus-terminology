import React from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Box, Button, TextField, Typography } from '@mui/material'
import APIService from '../../services/APIService'

// The API owns institution validation and creates only unverified ordinary accounts.
const LocalSignup = () => {
  const { t } = useTranslation()
  const [fields, setFields] = React.useState({username: '', email: '', password: ''})
  const [errors, setErrors] = React.useState({})
  const [busy, setBusy] = React.useState(false)
  const [created, setCreated] = React.useState(false)
  const submit = async event => {
    event.preventDefault()
    if(busy) return
    setBusy(true)
    setErrors({})
    try {
      await APIService.users().signup().request('POST', fields, false, {timeout: 20000})
      setCreated(true)
    } catch(error) {
      const data = error.response?.data
      setErrors(error.response?.status === 400 && data && typeof data === 'object' ?
        data : {detail: t('auth.signup_error')})
    } finally {
      setFields(previous => ({...previous, password: ''}))
      setBusy(false)
    }
  }
  const errorText = name => {
    const value = errors[name]
    return Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : ''
  }
  return (
    <Box component='form' onSubmit={submit} sx={{maxWidth: 440, mx: 'auto', my: 6, p: 3, display: 'grid', gap: 2}}>
      <Typography component='h1' variant='h5'>{t('auth.create_account')}</Typography>
      <Typography>{t('auth.institutional_signup')}</Typography>
      {created ? <Alert severity='success'>{t('auth.signup_check_email')}</Alert> : <>
        {(errors.detail || errors.non_field_errors) &&
          <Alert severity='error'>{errorText('detail') || errorText('non_field_errors')}</Alert>}
        {['username', 'email', 'password'].map(name => (
          <TextField key={name} name={name} label={t(`auth.${name}`)} required disabled={busy}
            type={name === 'password' ? 'password' : name === 'email' ? 'email' : 'text'}
            autoComplete={name === 'password' ? 'new-password' : name}
            value={fields[name]} error={Boolean(errors[name])} helperText={errorText(name)}
            onChange={event => setFields({...fields, [name]: event.target.value})} />
        ))}
        <Button variant='contained' type='submit' disabled={busy}>{t('auth.create_account')}</Button>
      </>}
      <Button href='#/signin'>{t('auth.sign_in')}</Button>
    </Box>
  )
}

export default LocalSignup
