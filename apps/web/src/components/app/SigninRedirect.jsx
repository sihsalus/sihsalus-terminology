import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Button } from '@mui/material'
import { getLoginURL, isSSOConfigured } from '../../common/utils'
import LocalSignIn from '../users/LocalSignIn'

const SigninRedirect = props => {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const sso = isSSOConfigured()
    const queryParams = new URLSearchParams(props.location?.search)
    if(!sso && !queryParams.has('returnTo')) return
    let active = true
    setFailed(false)
    getLoginURL(queryParams.get('returnTo'))
      .then(url => { if(active && sso) window.location.href = url })
      .catch(() => { if(active) setFailed(true) })
    return () => { active = false }
  }, [attempt, props.location?.search]);

  if(!isSSOConfigured() && !failed) return <LocalSignIn />
  return failed ?
    <Alert severity='error' action={<Button onClick={() => setAttempt(value => value + 1)}>{t('common.try_again')}</Button>}>{t('auth.redirect_failed')}</Alert> :
    <h4 role='status'>{t('auth.redirecting')}</h4>
};

export default SigninRedirect;
